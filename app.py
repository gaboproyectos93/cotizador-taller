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

# ==========================================
# 1. CONFIGURACIÓN Y CONEXIÓN
# ==========================================
st.set_page_config(page_title="Gestión de Flotas C.H.", layout="wide", page_icon="🚑")

NOMBRE_HOJA_GOOGLE = "DB_Cotizador_Ambulancias"
NUMERO_BASE = 1500 

@st.cache_resource
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
# 2. MOTOR DE DATOS (HISTORIAL Y AUTOCOMPLETADO)
# ==========================================
@st.cache_data(ttl=120) # Guarda la base de datos en memoria por 2 minutos para que sea rapidísimo
def obtener_base_datos():
    client = conectar_google_sheets()
    if client:
        try:
            sheet = client.open(NOMBRE_HOJA_GOOGLE)
            ws = sheet.worksheet("Historial")
            data = ws.get_all_values()
            if len(data) > 1:
                return pd.DataFrame(data[1:], columns=data[0])
        except Exception: pass
    return pd.DataFrame()

def obtener_y_registrar_correlativo(cliente, patente, marca, modelo, tiempo_ejecucion, total):
    client = conectar_google_sheets()
    if client:
        try:
            spreadsheet = client.open(NOMBRE_HOJA_GOOGLE)
            try: worksheet_hist = spreadsheet.worksheet("Historial")
            except:
                worksheet_hist = spreadsheet.add_worksheet(title="Historial", rows="1000", cols="8")
                # Actualizamos las columnas para guardar más datos y hacer el autocompletado más inteligente
                worksheet_hist.append_row(["Fecha", "Hora", "Correlativo", "Cliente", "Patente", "Marca", "Modelo", "Monto Total"])
            
            datos = worksheet_hist.get_all_values()
            numero_actual = len(datos) 
            correlativo_str = str(NUMERO_BASE + numero_actual)
            
            ahora = datetime.now()
            # Guardamos con Marca y Modelo para el futuro
            worksheet_hist.append_row([ahora.strftime("%d/%m/%Y"), ahora.strftime("%H:%M:%S"), correlativo_str, cliente.upper(), patente.upper(), marca.upper(), modelo.upper(), total])
            return correlativo_str
        except Exception: return "ERR"
    else: return "OFFLINE"

# --- MÓDULO DE BORRADORES AUTOMÁTICOS ---
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
# 3. IDENTIDAD CLÍNICA (CSS) Y CATÁLOGO
# ==========================================
EMPRESA_NOMBRE = "TALLER AUTOMOTRIZ C.H."
EMPRESA_TITULAR = "Especialistas en Vehículos de Emergencia y Rescate"

# Colores Clínicos Institucionales
COLOR_PRIMARIO = "#0A2540" # Azul Marino Institucional
COLOR_SECUNDARIO = "#00A4E4" # Celeste Médico

CATALOGO_AMBULANCIAS = {
    "--- Seleccione un servicio rápido ---": 0,
    "Mantención Preventiva (Aceite y Filtros)": 150000,
    "Cambio de Pastillas de Freno (Eje Delantero)": 85000,
    "Revisión y Ajuste de Balizas/Sirena": 45000,
    "Cambio Batería 100Ah (Uso Médico)": 120000,
    "Diagnóstico Computarizado (Scanner)": 35000,
    "Sanitización de Cabina Médica (Ozono)": 25000,
    "Recarga Sistema Oxígeno Central": 60000,
    "Revisión Tren Delantero": 40000
}

st.markdown(f"""
<style>
    .stContainer {{ border: 1px solid rgba(128, 128, 128, 0.2); border-radius: 8px; padding: 10px; margin-bottom: 5px; }}
    /* Botones primarios en Azul Marino */
    .stButton > button[kind="primary"] {{ background-color: {COLOR_PRIMARIO} !important; border-color: {COLOR_PRIMARIO} !important; color: white !important; font-weight: bold; }}
    .stButton > button[kind="primary"]:hover {{ background-color: {COLOR_SECUNDARIO} !important; border-color: {COLOR_SECUNDARIO} !important; }}
    
    /* Marca Blanca */
    #MainMenu {{ visibility: hidden !important; }}
    footer {{ display: none !important; }}
    header {{ display: none !important; }}
    .stDeployButton {{ display: none !important; }}
    div[data-testid="stToolbar"] {{ display: none !important; }}
    div[data-testid="stDecoration"] {{ display: none !important; }}
    div[data-testid="stStatusWidget"] {{ display: none !important; }}
    div[class^="viewerBadge"] {{ display: none !important; }}
    #st-cloud-logo {{ display: none !important; }}
</style>
""", unsafe_allow_html=True)

def format_clp(value):
    try: return f"${float(value):,.0f}".replace(",", ".")
    except: return "$0"

def reset_session():
    limpiar_borrador_nube()
    st.cache_data.clear() # Limpiamos la caché para traer datos frescos
    st.query_params.clear()
    for key in list(st.session_state.keys()): del st.session_state[key]
    st.rerun()

# ==========================================
# 4. PDF AMBULANCIAS (DISEÑO CORPORATIVO CLÍNICO)
# ==========================================
class PDF(FPDF):
    def __init__(self, correlativo=""):
        super().__init__()
        self.correlativo = correlativo

    def header(self):
        # Cuadro Superior Derecho (Azul Institucional)
        self.set_xy(130, 10); self.set_font('Arial', 'B', 14)
        self.set_text_color(255, 255, 255); self.set_fill_color(10, 37, 64) # Fondo Azul Marino
        titulo = f"PRESUPUESTO N° {self.correlativo}" if self.correlativo else "PRESUPUESTO"
        self.cell(70, 10, titulo, 1, 1, 'C', 1)
        
        self.set_text_color(0, 0, 0)
        self.set_xy(130, 20); self.set_font('Arial', '', 10)
        self.cell(70, 8, f"Fecha Emisión: {datetime.now().strftime('%d/%m/%Y')}", 1, 1, 'C')

        # Textos de Empresa
        self.set_xy(10, 10); self.set_font('Arial', 'B', 16) 
        self.set_text_color(10, 37, 64) # Azul Marino
        self.cell(115, 8, EMPRESA_NOMBRE, 0, 1, 'L')
        self.set_font('Arial', '', 10); self.set_text_color(0, 0, 0)
        self.cell(115, 5, EMPRESA_TITULAR, 0, 1, 'L')
        self.ln(10)

def generar_pdf_clinico(cliente, patente, marca, modelo, tiempo_ejec, items):
    pdf = PDF(correlativo=st.session_state.get('correlativo_temp', 'BORRADOR'))
    pdf.add_page(); pdf.set_auto_page_break(auto=True, margin=30) 
    
    # Identificación del Vehículo
    pdf.set_font('Arial', 'B', 11); pdf.set_fill_color(0, 164, 228); pdf.set_text_color(255, 255, 255) # Celeste Médico
    pdf.cell(0, 8, " 1. IDENTIFICACIÓN DE LA UNIDAD Y CLIENTE", 1, 1, 'L', 1)
    
    pdf.set_font('Arial', 'B', 10); pdf.set_text_color(0,0,0)
    pdf.cell(35, 7, "INSTITUCIÓN:", 'L', 0); pdf.set_font('Arial', '', 10); pdf.cell(0, 7, str(cliente).upper(), 'R', 1)
    
    pdf.set_font('Arial', 'B', 10); pdf.cell(35, 7, "PATENTE:", 'L', 0); pdf.set_font('Arial', '', 10); pdf.cell(45, 7, str(patente).upper(), 0, 0)
    pdf.set_font('Arial', 'B', 10); pdf.cell(25, 7, "VEHÍCULO:", 0, 0); pdf.set_font('Arial', '', 10); pdf.cell(0, 7, f"{str(marca).upper()} {str(modelo).upper()}", 'R', 1)
    
    pdf.set_font('Arial', 'B', 10); pdf.cell(35, 7, "TIEMPO ESTIM.:", 'L,B', 0); pdf.set_font('Arial', '', 10); pdf.cell(0, 7, str(tiempo_ejec).upper(), 'R,B', 1)
    pdf.ln(6)
    
    # Tabla ítems
    pdf.set_font('Arial', 'B', 11); pdf.set_fill_color(10, 37, 64); pdf.set_text_color(255,255,255) # Azul Marino
    pdf.cell(0, 8, " 2. DETALLE TÉCNICO DE REPARACIÓN", 1, 1, 'L', 1)
    
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(110, 8, "DESCRIPCIÓN DE REPARACIÓN / REPUESTO", 1, 0, 'C', 1)
    pdf.cell(20, 8, "CANT.", 1, 0, 'C', 1); pdf.cell(30, 8, "P. UNIT.", 1, 0, 'C', 1); pdf.cell(30, 8, "TOTAL", 1, 1, 'C', 1)
    
    pdf.set_text_color(0,0,0); pdf.set_font('Arial', '', 9)
    total_neto = 0
    for item in items:
        x = pdf.get_x(); y = pdf.get_y()
        pdf.multi_cell(110, 6, item['Descripción'].upper(), 1, 'L')
        h = pdf.get_y() - y; pdf.set_xy(x+110, y)
        pdf.cell(20, h, str(item['Cantidad']), 1, 0, 'C'); pdf.cell(30, h, format_clp(item['Unitario']), 1, 0, 'R'); pdf.cell(30, h, format_clp(item['Total']), 1, 0, 'R')
        pdf.set_xy(x, y + h); total_neto += item['Total']

    iva = total_neto * 0.19; total = total_neto + iva
    pdf.ln(2)
    pdf.set_x(130); pdf.cell(40, 7, "Neto:", 1, 0, 'L'); pdf.cell(30, 7, format_clp(total_neto), 1, 1, 'R')
    pdf.set_x(130); pdf.cell(40, 7, "IVA (19%):", 1, 0, 'L'); pdf.cell(30, 7, format_clp(iva), 1, 1, 'R')
    pdf.set_x(130); pdf.set_font('Arial', 'B', 10); pdf.set_fill_color(230,230,230)
    pdf.cell(40, 8, "TOTAL:", 1, 0, 'L', 1); pdf.cell(30, 8, format_clp(total), 1, 1, 'R', 1)

    # Cláusula de Calidad Clínica
    pdf.ln(12); pdf.set_font('Arial', 'B', 9); pdf.set_text_color(10, 37, 64)
    pdf.cell(0, 5, "GARANTÍA Y COMPROMISO DE CALIDAD", 0, 1, 'L')
    pdf.set_font('Arial', '', 8); pdf.set_text_color(0,0,0)
    pdf.multi_cell(0, 4, "Los repuestos y componentes mecánicos utilizados en este presupuesto cumplen con los estándares de seguridad requeridos para la correcta operación de vehículos de emergencia y rescate. Los trabajos mecánicos cuentan con 3 meses de garantía por mano de obra.")

    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 5. UI PRINCIPAL (GESTIÓN DE FLOTAS)
# ==========================================
with st.sidebar:
    st.markdown("## 🚑 Taller Ambulancias")
    st.markdown("---")
    if st.button("🗑️ Nueva Cotización", type="primary", use_container_width=True): reset_session()

# Verificador de Borradores
if 'check_borrador' not in st.session_state:
    st.session_state.check_borrador = True
    borrador_recuperado = cargar_borrador_nube()
    if borrador_recuperado and 'cliente_confirmado' in borrador_recuperado:
        st.session_state.borrador_pendiente = borrador_recuperado

# Inicializamos variables de autocompletado si no existen
if 'auto_cliente' not in st.session_state: st.session_state.auto_cliente = ""
if 'auto_marca' not in st.session_state: st.session_state.auto_marca = ""
if 'auto_modelo' not in st.session_state: st.session_state.auto_modelo = ""
if 'patente_buscada' not in st.session_state: st.session_state.patente_buscada = ""

if 'paso_actual' not in st.session_state: st.session_state.paso_actual = 1

col_centro = st.columns([1, 2, 1])
with col_centro[1]:
    
    # --- BARRA DE PROGRESO VISUAL ---
    if st.session_state.paso_actual == 1:
        st.markdown(f"**<span style='color:{COLOR_SECUNDARIO};'>🔵 1. Recepción de Flota</span>** ➔ ⚪ 2. Diagnóstico ➔ ⚪ 3. Presupuesto", unsafe_allow_html=True)
    elif st.session_state.paso_actual == 2:
        st.markdown(f"✅ 1. Recepción de Flota ➔ **<span style='color:{COLOR_SECUNDARIO};'>🔵 2. Diagnóstico</span>** ➔ ⚪ 3. Presupuesto", unsafe_allow_html=True)
    st.markdown("---")

    # --- PASO 1: DATOS Y CRM DE FLOTAS ---
    if st.session_state.paso_actual == 1:
        
        # ALERTA DE BORRADOR
        if 'borrador_pendiente' in st.session_state:
            st.error(f"⚠️ ¡ATENCIÓN! Tienes una cotización en pausa para la unidad **{st.session_state.borrador_pendiente.get('patente_confirmada', 'Desconocida')}**.")
            ca, cb = st.columns(2)
            if ca.button("✅ Recuperar Trabajo", use_container_width=True):
                for k, v in st.session_state.borrador_pendiente.items(): st.session_state[k] = v
                del st.session_state['borrador_pendiente']
                st.rerun()
            if cb.button("🗑️ Descartar y empezar de cero", use_container_width=True):
                limpiar_borrador_nube(); del st.session_state['borrador_pendiente']; st.rerun()
            st.markdown("---")

        st.title("Recepción de Flota")
        
        # BUSCADOR INTELIGENTE
        st.markdown("**1. Búsqueda Rápida (Historial Clínico de la Ambulancia)**")
        col_b1, col_b2 = st.columns([3, 1])
        patente_input = col_b1.text_input("Patente de la Ambulancia", placeholder="Ej: AB-CD-12", value=st.session_state.patente_buscada)
        
        # Le damos un margin-top al botón para alinearlo con el input
        st.markdown("""<style>div.stButton > button:first-child { margin-top: 28px; }</style>""", unsafe_allow_html=True)
        if col_b2.button("🔍 Buscar Historial", use_container_width=True):
            if patente_input:
                st.session_state.patente_buscada = patente_input
                df_historial = obtener_base_datos()
                if not df_historial.empty and "Patente" in df_historial.columns:
                    # Filtramos por patente exacta (ignorando mayúsculas)
                    df_filtrado = df_historial[df_historial["Patente"].str.upper() == patente_input.upper()]
                    if not df_filtrado.empty:
                        # Extraemos los datos más recientes para autocompletar
                        ultimo_registro = df_filtrado.iloc[-1]
                        st.session_state.auto_cliente = ultimo_registro.get("Cliente", "")
                        st.session_state.auto_marca = ultimo_registro.get("Marca", "")
                        st.session_state.auto_modelo = ultimo_registro.get("Modelo", "")
                        
                        st.success(f"✅ ¡Ambulancia encontrada! Registra {len(df_filtrado)} ingresos previos.")
                        # Mostramos el historial médico rápido en una tabla pequeña
                        st.dataframe(df_filtrado[["Fecha", "Correlativo", "Monto Total"]].tail(3), use_container_width=True, hide_index=True)
                    else:
                        st.info("ℹ️ Primera vez que ingresa esta patente al taller.")
                        st.session_state.auto_cliente = ""; st.session_state.auto_marca = ""; st.session_state.auto_modelo = ""
            else:
                st.warning("⚠️ Escribe una patente para buscar.")
        
        st.markdown("---")
        st.markdown("**2. Datos de la Institución y Vehículo**")
        # Los inputs toman el value del session_state para autocompletarse si se encontró la patente
        cliente = st.text_input("Institución / Hospital", placeholder="Ej: Hospital Regional...", value=st.session_state.auto_cliente)
        c1, c2 = st.columns(2)
        marca = c1.text_input("Marca", placeholder="Ej: Mercedes-Benz", value=st.session_state.auto_marca)
        modelo = c2.text_input("Modelo", placeholder="Ej: Sprinter 313", value=st.session_state.auto_modelo)
        
        st.markdown("**3. Compromiso de Entrega (SLA)**")
        tiempo_ejec = st.text_input("Tiempo Estimado de Reparación", placeholder="Ej: 48 Horas, 3 Días Hábiles...")
        
        if st.button("🚀 CONTINUAR AL DIAGNÓSTICO", type="primary", use_container_width=True):
            if not cliente or not patente_input: st.error("⛔ Ingrese Institución y Patente.")
            else:
                st.session_state.cliente_confirmado = cliente
                st.session_state.patente_confirmada = patente_input
                st.session_state.marca_confirmada = marca
                st.session_state.modelo_confirmado = modelo
                st.session_state.tiempo_confirmado = tiempo_ejec
                st.session_state.paso_actual = 2
                guardar_borrador_nube() 
                st.rerun()

    # --- PASO 2: DIAGNÓSTICO Y REPUESTOS ---
    elif st.session_state.paso_actual == 2:
        if 'items_manuales' not in st.session_state: st.session_state.items_manuales = []
        
        c1, c2 = st.columns([1, 4])
        with c1: 
            if st.button("⬅️ Volver"): st.session_state.paso_actual = 1; st.rerun()
        with c2: st.markdown(f"### 🚑 {st.session_state.patente_confirmada.upper()} | {st.session_state.cliente_confirmado}")
        
        st.markdown("---")
        
        # LIMPIEZA VISUAL: EXPANDERS
        with st.expander("⚡ ABRIR CATÁLOGO RÁPIDO DE SERVICIOS", expanded=True):
            st.markdown("Selecciona un servicio frecuente:")
            opcion_cat = st.selectbox("Servicios y Repuestos Frecuentes", list(CATALOGO_AMBULANCIAS.keys()), label_visibility="collapsed")
            col_c1, col_c2 = st.columns(2)
            cant_cat = col_c1.number_input("Cantidad", min_value=1, value=1, key="cant_cat")
            
            if opcion_cat != "--- Seleccione un servicio rápido ---":
                st.info(f"Precio Unitario Sugerido: **{format_clp(CATALOGO_AMBULANCIAS[opcion_cat])}**")
                
            if st.button("➕ Agregar al Diagnóstico", type="secondary", use_container_width=True):
                if opcion_cat != "--- Seleccione un servicio rápido ---":
                    st.session_state.items_manuales.append({
                        "Descripción": opcion_cat, "Cantidad": cant_cat, 
                        "Unitario": CATALOGO_AMBULANCIAS[opcion_cat], "Total": CATALOGO_AMBULANCIAS[opcion_cat] * cant_cat
                    })
                    guardar_borrador_nube(); st.rerun()
                else: st.warning("⚠️ Selecciona un servicio de la lista primero.")

        with st.expander("✍️ INGRESAR REPUESTO O SERVICIO MANUAL", expanded=False):
            d_m = st.text_input("Descripción específica", placeholder="Ej: Cambio de balata trasera...")
            col_m1, col_m2 = st.columns(2)
            q_m = col_m1.number_input("Cantidad", min_value=1, value=1, key="cant_man")
            p_m = col_m2.number_input("Precio Unitario Neto ($)", min_value=0, value=None, step=1000)
            
            if st.button("➕ Agregar Ítem Manual", type="secondary", use_container_width=True):
                if d_m and p_m is not None:
                    st.session_state.items_manuales.append({"Descripción": d_m.upper(), "Cantidad": q_m, "Unitario": p_m, "Total": p_m * q_m})
                    guardar_borrador_nube(); st.rerun()
                else: st.warning("⚠️ Faltan datos.")

        # LISTA DE TRABAJOS
        if st.session_state.items_manuales:
            st.markdown("---")
            st.markdown("###### Detalle de Trabajos a Realizar:")
            for idx, item in enumerate(st.session_state.items_manuales):
                st.text(f"• {item['Cantidad']}x {item['Descripción']} | {format_clp(item['Total'])}")
            
            if st.button("🗑️ Vaciar Lista"): 
                st.session_state.items_manuales = []; guardar_borrador_nube(); st.rerun()

            total_neto = sum(x['Total'] for x in st.session_state.items_manuales)
            st.subheader(f"📊 TOTAL A PAGAR: {format_clp(total_neto * 1.19)}")

            if 'presupuesto_generado' not in st.session_state:
                if st.button("💾 GENERAR PRESUPUESTO OFICIAL", type="primary", use_container_width=True):
                    correlativo = obtener_y_registrar_correlativo(st.session_state.cliente_confirmado, st.session_state.patente_confirmada, st.session_state.marca_confirmada, st.session_state.modelo_confirmado, st.session_state.tiempo_confirmado, format_clp(total_neto * 1.19))
                    st.session_state['correlativo_temp'] = correlativo
                    
                    pdf_bytes = generar_pdf_clinico(st.session_state.cliente_confirmado, st.session_state.patente_confirmada, st.session_state.marca_confirmada, st.session_state.modelo_confirmado, st.session_state.tiempo_confirmado, st.session_state.items_manuales)
                    st.session_state['presupuesto_generado'] = {'pdf': pdf_bytes, 'nombre': f"Presupuesto {correlativo} - {st.session_state.patente_confirmada}.pdf"}
                    limpiar_borrador_nube(); st.rerun()
            else:
                data = st.session_state['presupuesto_generado']
                st.success(f"✅ Presupuesto N° {st.session_state['correlativo_temp']} generado exitosamente.")
                st.download_button("📥 DESCARGAR PDF", data['pdf'], data['nombre'], "application/pdf", type="primary", use_container_width=True)
