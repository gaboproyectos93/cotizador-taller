import streamlit as st
import pandas as pd
import io
import os
import json
from fpdf import FPDF
from datetime import datetime
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from PIL import Image, ImageOps

# ==========================================
# 1. CONFIGURACIÓN Y CONEXIÓN
# ==========================================
st.set_page_config(page_title="Cotizador Ambulancias", layout="wide", page_icon="🚑")

# Asegúrate de que este sea el nombre correcto del Google Sheet de Cristian
NOMBRE_HOJA_GOOGLE = "DB_Cotizador_Ambulancias"

# ¡AQUÍ ESTÁ LA MAGIA DEL NÚMERO DE COTIZACIÓN!
NUMERO_BASE = 1500 

def conectar_google_sheets():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    try:
        if "gcp_service_account" in st.secrets:
            creds_dict = st.secrets["gcp_service_account"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            return gspread.authorize(creds)
        return None
    except Exception as e: 
        st.error(f"❌ ERROR: Revisa los Secrets. Detalle: {e}")
        return None

# ==========================================
# 2. CORRELATIVOS Y BORRADORES (AUTO-SAVE)
# ==========================================
def obtener_y_registrar_correlativo(cliente, patente, total):
    client = conectar_google_sheets()
    if client:
        try:
            spreadsheet = client.open(NOMBRE_HOJA_GOOGLE)
            try: worksheet_hist = spreadsheet.worksheet("Historial")
            except:
                worksheet_hist = spreadsheet.add_worksheet(title="Historial", rows="1000", cols="6")
                worksheet_hist.append_row(["Fecha", "Hora", "Correlativo", "Cliente", "Patente", "Monto Total"])
            
            datos = worksheet_hist.get_all_values()
            # El correlativo ahora suma la cantidad de filas + el NUMERO BASE
            numero_actual = len(datos) 
            correlativo_str = str(NUMERO_BASE + numero_actual)
            
            ahora = datetime.now()
            worksheet_hist.append_row([ahora.strftime("%d/%m/%Y"), ahora.strftime("%H:%M:%S"), correlativo_str, cliente.upper(), patente.upper(), total])
            return correlativo_str
        except Exception: return "ERR"
    else: return "OFFLINE"

def guardar_borrador_nube():
    client = conectar_google_sheets()
    if not client: return
    try:
        sheet = client.open(NOMBRE_HOJA_GOOGLE)
        try: ws = sheet.worksheet("Borrador")
        except: ws = sheet.add_worksheet(title="Borrador", rows="2", cols="2")
        datos = {k: v for k, v in st.session_state.items() if k.endswith('_confirmado') or k == 'paso_actual' or k == 'items_manuales'}
        ws.update_acell('A1', json.dumps(datos))
    except Exception: pass

def cargar_borrador_nube():
    client = conectar_google_sheets()
    if not client: return None
    try:
        sheet = client.open(NOMBRE_HOJA_GOOGLE)
        ws = sheet.worksheet("Borrador")
        val = ws.acell('A1').value
        if val: return json.loads(val)
    except Exception: pass
    return None

def limpiar_borrador_nube():
    client = conectar_google_sheets()
    if not client: return
    try:
        sheet = client.open(NOMBRE_HOJA_GOOGLE)
        ws = sheet.worksheet("Borrador")
        ws.update_acell('A1', '')
    except Exception: pass

# ==========================================
# 3. CATÁLOGO DE PRECIOS Y ESTILOS
# ==========================================
# Aquí puedes editar los ítems y precios exactos que te pida Cristian
CATALOGO_AMBULANCIAS = {
    "--- Seleccione un servicio rápido ---": 0,
    "Mantención Preventiva (Aceite y Filtros)": 150000,
    "Cambio de Pastillas de Freno (Eje Delantero)": 85000,
    "Revisión y Ajuste de Balizas/Sirena": 45000,
    "Cambio Batería 100Ah (Uso Médico)": 120000,
    "Diagnóstico Computarizado (Scanner)": 35000,
    "Sanitización de Cabina Médica": 25000,
    "Recarga Sistema Oxígeno Central": 60000,
    "Revisión Tren Delantero": 40000
}

EMPRESA_NOMBRE = "TALLER AUTOMOTRIZ C.H." # Cambiar por el nombre real
EMPRESA_TITULAR = "Especialistas en Vehículos de Emergencia"

st.markdown("""
<style>
    .stContainer { border: 1px solid rgba(128, 128, 128, 0.2); border-radius: 8px; padding: 10px; margin-bottom: 5px; }
    .stButton > button[kind="primary"] { background-color: #D32F2F !important; color: white !important; font-weight: bold; }
    #MainMenu { visibility: hidden; } footer { display: none; } header { display: none; }
</style>
""", unsafe_allow_html=True)

def format_clp(value):
    try: return f"${float(value):,.0f}".replace(",", ".")
    except: return "$0"

def reset_session():
    limpiar_borrador_nube()
    st.query_params.clear()
    for key in list(st.session_state.keys()): del st.session_state[key]
    st.rerun()

# ==========================================
# 4. PDF AMBULANCIAS
# ==========================================
class PDF(FPDF):
    def __init__(self, correlativo=""):
        super().__init__()
        self.correlativo = correlativo

    def header(self):
        self.set_xy(130, 10); self.set_font('Arial', 'B', 14)
        titulo = f"PRESUPUESTO N° {self.correlativo}" if self.correlativo else "PRESUPUESTO"
        self.cell(70, 10, titulo, 1, 1, 'C')
        self.set_xy(130, 20); self.set_font('Arial', '', 10)
        self.cell(70, 8, f"Fecha: {datetime.now().strftime('%d/%m/%Y')}", 1, 1, 'C')

        self.set_xy(10, 10); self.set_font('Arial', 'B', 16) 
        self.cell(115, 8, EMPRESA_NOMBRE, 0, 1, 'L')
        self.set_font('Arial', '', 10)
        self.cell(115, 5, EMPRESA_TITULAR, 0, 1, 'L')
        self.ln(10)

def generar_pdf(cliente, patente, marca, modelo, items):
    pdf = PDF(correlativo=st.session_state.get('correlativo_temp', 'BORRADOR'))
    pdf.add_page()
    
    # Identificación
    pdf.set_font('Arial', 'B', 11); pdf.set_fill_color(230, 230, 230)
    pdf.cell(0, 8, " DATOS DEL VEHÍCULO Y CLIENTE", 1, 1, 'L', 1)
    
    pdf.set_font('Arial', 'B', 10); pdf.cell(30, 7, "CLIENTE:", 'L', 0)
    pdf.set_font('Arial', '', 10); pdf.cell(0, 7, str(cliente).upper(), 'R', 1)
    
    pdf.set_font('Arial', 'B', 10); pdf.cell(30, 7, "PATENTE:", 'L', 0)
    pdf.set_font('Arial', '', 10); pdf.cell(40, 7, str(patente).upper(), 0, 0)
    pdf.set_font('Arial', 'B', 10); pdf.cell(20, 7, "VEHÍCULO:", 0, 0)
    pdf.set_font('Arial', '', 10); pdf.cell(0, 7, f"{str(marca).upper()} {str(modelo).upper()}", 'R', 1)
    
    # Tabla Inferior (El borde inferior para cerrar la caja de identificación)
    pdf.cell(0, 0, "", 'T', 1) 
    pdf.ln(5)
    
    # Tabla ítems
    pdf.set_font('Arial', 'B', 10); pdf.set_fill_color(200, 0, 0); pdf.set_text_color(255,255,255)
    pdf.cell(110, 8, "DESCRIPCIÓN DE REPARACIÓN", 1, 0, 'C', 1)
    pdf.cell(20, 8, "CANT.", 1, 0, 'C', 1)
    pdf.cell(30, 8, "P. UNIT.", 1, 0, 'C', 1)
    pdf.cell(30, 8, "TOTAL", 1, 1, 'C', 1)
    
    pdf.set_text_color(0,0,0); pdf.set_font('Arial', '', 9)
    total_neto = 0
    for item in items:
        x = pdf.get_x(); y = pdf.get_y()
        pdf.multi_cell(110, 6, item['Descripción'].upper(), 1, 'L')
        h = pdf.get_y() - y; pdf.set_xy(x+110, y)
        pdf.cell(20, h, str(item['Cantidad']), 1, 0, 'C')
        pdf.cell(30, h, format_clp(item['Unitario']), 1, 0, 'R')
        pdf.cell(30, h, format_clp(item['Total']), 1, 0, 'R')
        pdf.set_xy(x, y + h)
        total_neto += item['Total']

    iva = total_neto * 0.19; total = total_neto + iva
    pdf.ln(2)
    pdf.set_x(130); pdf.cell(40, 7, "Neto:", 1, 0, 'L'); pdf.cell(30, 7, format_clp(total_neto), 1, 1, 'R')
    pdf.set_x(130); pdf.cell(40, 7, "IVA (19%):", 1, 0, 'L'); pdf.cell(30, 7, format_clp(iva), 1, 1, 'R')
    pdf.set_x(130); pdf.set_font('Arial', 'B', 10)
    pdf.cell(40, 8, "TOTAL:", 1, 0, 'L'); pdf.cell(30, 8, format_clp(total), 1, 1, 'R')

    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 5. UI PRINCIPAL
# ==========================================
with st.sidebar:
    st.markdown("## 🚑 Taller Ambulancias")
    st.markdown("---")
    if st.button("🗑️ Nueva Cotización", type="primary", use_container_width=True): reset_session()

# --- VERIFICADOR DE BORRADORES AUTOMÁTICO ---
if 'check_borrador' not in st.session_state:
    st.session_state.check_borrador = True
    borrador_recuperado = cargar_borrador_nube()
    if borrador_recuperado and 'cliente_confirmado' in borrador_recuperado:
        st.session_state.borrador_pendiente = borrador_recuperado

if 'paso_actual' not in st.session_state: st.session_state.paso_actual = 1

# --- PASO 1: DATOS ---
if st.session_state.paso_actual == 1:
    col_centro = st.columns([1, 2, 1])
    with col_centro[1]:
        # ALERTA DE BORRADOR
        if 'borrador_pendiente' in st.session_state:
            st.error(f"⚠️ ¡ATENCIÓN! Tienes una cotización en pausa para la patente **{st.session_state.borrador_pendiente.get('patente_confirmada', 'Desconocida')}**.")
            ca, cb = st.columns(2)
            if ca.button("✅ Recuperar Trabajo", use_container_width=True):
                for k, v in st.session_state.borrador_pendiente.items(): st.session_state[k] = v
                del st.session_state['borrador_pendiente']
                st.rerun()
            if cb.button("🗑️ Descartar y empezar de cero", use_container_width=True):
                limpiar_borrador_nube()
                del st.session_state['borrador_pendiente']
                st.rerun()
            st.markdown("---")

        st.title("Cotizador de Taller")
        cliente = st.text_input("Cliente / Institución", placeholder="Ej: Hospital Regional...")
        patente = st.text_input("Patente del Vehículo", placeholder="Ej: AB-CD-12")
        c1, c2 = st.columns(2)
        marca = c1.text_input("Marca", placeholder="Ej: Mercedes-Benz")
        modelo = c2.text_input("Modelo", placeholder="Ej: Sprinter 313")
        
        if st.button("🚀 CONTINUAR A REPUESTOS", type="primary", use_container_width=True):
            if not cliente or not patente: st.error("⛔ Ingrese Cliente y Patente.")
            else:
                st.session_state.cliente_confirmado = cliente
                st.session_state.patente_confirmada = patente
                st.session_state.marca_confirmada = marca
                st.session_state.modelo_confirmado = modelo
                st.session_state.paso_actual = 2
                guardar_borrador_nube() # Guardado Silencioso
                st.rerun()

# --- PASO 2: COTIZADOR ---
elif st.session_state.paso_actual == 2:
    if 'items_manuales' not in st.session_state: st.session_state.items_manuales = []
    
    c1, c2 = st.columns([1, 5])
    with c1: 
        if st.button("⬅️ Volver"): st.session_state.paso_actual = 1; st.rerun()
    with c2: st.markdown(f"### 🚑 {st.session_state.patente_confirmada.upper()} | {st.session_state.cliente_confirmado}")
    
    st.markdown("---")
    
    # --- NUEVO: PESTAÑAS PARA CATÁLOGO VS MANUAL ---
    tab1, tab2 = st.tabs(["⚡ Catálogo Rápido", "✍️ Ingreso Manual"])
    
    with tab1:
        st.markdown("Selecciona un servicio frecuente para agregarlo al instante:")
        opcion_cat = st.selectbox("Servicios y Repuestos Frecuentes", list(CATALOGO_AMBULANCIAS.keys()))
        col_c1, col_c2 = st.columns(2)
        cant_cat = col_c1.number_input("Cantidad", min_value=1, value=1, key="cant_cat")
        
        # Muestra el precio que se va a cobrar
        if opcion_cat != "--- Seleccione un servicio rápido ---":
            st.info(f"Precio Unitario Sugerido: **{format_clp(CATALOGO_AMBULANCIAS[opcion_cat])}**")
            
        if st.button("➕ Agregar desde Catálogo", type="secondary"):
            if opcion_cat != "--- Seleccione un servicio rápido ---":
                st.session_state.items_manuales.append({
                    "Descripción": opcion_cat, 
                    "Cantidad": cant_cat, 
                    "Unitario": CATALOGO_AMBULANCIAS[opcion_cat], 
                    "Total": CATALOGO_AMBULANCIAS[opcion_cat] * cant_cat
                })
                guardar_borrador_nube()
                st.success("✅ Servicio agregado.")
                time.sleep(0.5)
                st.rerun()
            else:
                st.warning("⚠️ Selecciona un servicio de la lista primero.")

    with tab2:
        d_m = st.text_input("Descripción específica", placeholder="Ej: Reparación a medida...")
        col_m1, col_m2 = st.columns(2)
        q_m = col_m1.number_input("Cantidad", min_value=1, value=1, key="cant_man")
        p_m = col_m2.number_input("Precio Unitario Neto ($)", min_value=0, value=None, step=1000)
        
        if st.button("➕ Agregar Ítem Manual", type="secondary"):
            if d_m and p_m is not None:
                st.session_state.items_manuales.append({"Descripción": d_m.upper(), "Cantidad": q_m, "Unitario": p_m, "Total": p_m * q_m})
                guardar_borrador_nube()
                st.success("✅ Ítem manual agregado.")
                time.sleep(0.5)
                st.rerun()
            else: st.warning("⚠️ Faltan datos.")

    if st.session_state.items_manuales:
        st.markdown("---")
        st.markdown("###### Lista de Trabajos:")
        for idx, item in enumerate(st.session_state.items_manuales):
            st.text(f"• {item['Cantidad']}x {item['Descripción']} | {format_clp(item['Total'])}")
        
        if st.button("🗑️ Borrar Todo"): 
            st.session_state.items_manuales = []
            guardar_borrador_nube()
            st.rerun()

        total_neto = sum(x['Total'] for x in st.session_state.items_manuales)
        st.subheader(f"📊 TOTAL A PAGAR: {format_clp(total_neto * 1.19)}")

        if 'presupuesto_generado' not in st.session_state:
            if st.button("💾 GENERAR PRESUPUESTO", type="primary", use_container_width=True):
                # El correlativo se genera aquí usando la base de 1500
                correlativo = obtener_y_registrar_correlativo(st.session_state.cliente_confirmado, st.session_state.patente_confirmada, format_clp(total_neto * 1.19))
                st.session_state['correlativo_temp'] = correlativo
                
                pdf_bytes = generar_pdf(st.session_state.cliente_confirmado, st.session_state.patente_confirmada, st.session_state.marca_confirmada, st.session_state.modelo_confirmado, st.session_state.items_manuales)
                st.session_state['presupuesto_generado'] = {'pdf': pdf_bytes, 'nombre': f"Presupuesto {correlativo} - {st.session_state.patente_confirmada}.pdf"}
                limpiar_borrador_nube() # Limpiamos porque ya terminó
                st.rerun()
        else:
            data = st.session_state['presupuesto_generado']
            st.success(f"✅ Presupuesto N° {st.session_state['correlativo_temp']} generado.")
            st.download_button("📥 DESCARGAR PDF", data['pdf'], data['nombre'], "application/pdf", type="primary", use_container_width=True)
