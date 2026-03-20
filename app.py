import streamlit as st
import pandas as pd
import io
import os
import json
import streamlit.components.v1 as components
from fpdf import FPDF
from datetime import datetime
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ==========================================
# 1. CONFIGURACIÓN Y CONEXIÓN A LA NUBE
# ==========================================
st.set_page_config(page_title="Gestión Flotas C.H.", layout="wide", page_icon="🚑")

NOMBRE_HOJA_GOOGLE = "DB_Cotizador"

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
# 2. LÓGICA ORIGINAL DE BASE DE DATOS (CSV)
# ==========================================
EMPRESA_NOMBRE = "CHRISTIAN HERRERA"
RUT_EMPRESA = "12.345.678-9" 
DIRECCION = "Temuco, Región de la Araucanía"
TELEFONO = "+56 9 1234 5678"
EMAIL = "c.h.servicioautomotriz@gmail.com"
ARCHIVO_DB = "lista_precios.csv"

def format_clp(value):
    try: return f"${float(value):,.0f}".replace(",", ".")
    except: return "$0"

def cargar_datos():
    datos_iniciales = """Categoria,Trabajo,Costo_SSAS,Venta_SSAS,Costo_Hosp,Venta_Hosp
Luces y Exterior,Cambiar focos Perimetrales,195000,273000,204750,276412.5
Luces y Exterior,Cambiar Focos Escena,195000,273000,204750,276412.5
Luces y Exterior,Cambiar foco Faenero,74900,108605,78645,114035.25
Luces y Exterior,Cambiar Balizas barral doble con accesorios,1485700,1931410,1559985,2027980.5
Luces y Exterior,Cambiar focos y sistema iluminación interior,68900,99905,72345,104900.25
Carrocería y Vidrios,Cambio de vidrio de puerta Corredera lateral,290000,391500,304500,411075
Carrocería y Vidrios,Láminas Seguridad 10 micras (Puertas),75000,108750,78750,114187.5
Carrocería y Vidrios,Láminas Seguridad 10 micras (Ventanas),75000,108750,78750,114187.5
Carrocería y Vidrios,Láminas Seguridad 4 micras (Parabrisas),120000,168000,126000,176400
Interior Sanitario,Cambio de luces interiores de gabinete sanitario,58000,84100,60900,88305
Interior Sanitario,Reparar línea de oxígeno central,180000,252000,189000,264600
Interior Sanitario,Reparar línea de aspiración de paciente,165000,231000,173250,242550
Interior Sanitario,Cambiar conjunto motor A/C gabinete,765000,994500,803250,1044225
Asientos y Tapiz,Tapizado de asiento de paramédico,125000,175000,131250,183750
Asientos y Tapiz,Tapizado de asiento longitudinal,90000,130500,94500,137025
Asientos y Tapiz,Cambio de asiento de paramédico,475800,642330,499590,674446.5
Asientos y Tapiz,Cambio de asiento longitudinal,160000,224000,168000,235200
Equipamiento y Radio,Instalar Radio Transmisor Antena y acc.,1143650,1486745,1200832.5,1561082.25
Equipamiento y Radio,Cambiar Sirena y Parlante con accesorios,893700,1161810,600000,780000
Equipamiento y Radio,Cambiar inversor de corriente (2500W),845000,1098500,887250,1153425
Equipamiento y Radio,Cambiar botonera accesorios emergencia,28900,41905,30345,44000.25
Cabina y Tablero,Reparar circuito eléctrico Tablero,180000,252000,189000,264600
Camilla,Tapizado de colchoneta de camilla,120000,168000,126000,176400
Camilla,Cambiar colchoneta de camilla,90000,130500,94500,137025
Camilla,Reparar Camilla (respaldo elevación),345800,466830,363090,490171.5
Camilla,Reparar Camilla (vástagos y pasadores),165765,232071,174053,243675
Camilla,Cambiar 1 Rueda de Camilla,135800,190120,142590,199626
Camilla,Aceitar y lubricar partes articuladas camilla,90000,130500,94500,137025"""
    if not os.path.exists(ARCHIVO_DB):
        df = pd.read_csv(io.StringIO(datos_iniciales))
        df.to_csv(ARCHIVO_DB, index=False, encoding='utf-8-sig')
        return df
    else: return pd.read_csv(ARCHIVO_DB, encoding='utf-8-sig')

def guardar_nuevo_item(categoria, nombre, costo):
    df_actual = cargar_datos()
    venta_ssas = costo * 1.40; costo_hosp = costo * 1.05; venta_hosp = venta_ssas * 1.05
    nuevo_row = pd.DataFrame([{"Categoria": categoria, "Trabajo": nombre, "Costo_SSAS": costo, "Venta_SSAS": venta_ssas, "Costo_Hosp": costo_hosp, "Venta_Hosp": venta_hosp}])
    df_nuevo = pd.concat([df_actual, nuevo_row], ignore_index=True)
    df_nuevo.to_csv(ARCHIVO_DB, index=False, encoding='utf-8-sig')
    return True

# ==========================================
# 3. HISTORIAL CLÍNICO Y BORRADORES (NUBE)
# ==========================================
@st.cache_data(ttl=60) 
def obtener_base_datos():
    client = conectar_google_sheets()
    if client:
        try:
            sheet = client.open(NOMBRE_HOJA_GOOGLE)
            ws = sheet.worksheet("Historial")
            data = ws.get_all_values()
            if len(data) > 1: return pd.DataFrame(data[1:], columns=data[0])
        except Exception: pass
    return pd.DataFrame()

def obtener_y_registrar_correlativo(cliente, patente, marca, modelo, sla, total):
    client = conectar_google_sheets()
    if client:
        try:
            spreadsheet = client.open(NOMBRE_HOJA_GOOGLE)
            try: worksheet_hist = spreadsheet.worksheet("Historial")
            except:
                worksheet_hist = spreadsheet.add_worksheet(title="Historial", rows="1000", cols="8")
                worksheet_hist.append_row(["Fecha", "Hora", "Correlativo", "Cliente", "Patente", "Marca", "Modelo", "Tiempo", "Total"])
            
            datos = worksheet_hist.get_all_values()
            numero_actual = len(datos) 
            correlativo_str = str(numero_actual) # ¡Correlativo como número entero real desde el inicio!
            
            ahora = datetime.now()
            worksheet_hist.append_row([ahora.strftime("%d/%m/%Y"), ahora.strftime("%H:%M:%S"), correlativo_str, cliente.upper(), patente.upper(), marca.upper(), modelo.upper(), sla, total])
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
        # Guardo todas las keys importantes para no perder nada (cantidades y campos confirmados)
        datos = {k: v for k, v in st.session_state.items() if k.endswith('_confirmado') or k.startswith('q_') or k == 'paso_actual'}
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

def reset_session():
    limpiar_borrador_nube()
    st.query_params.clear()
    for key in list(st.session_state.keys()): del st.session_state[key]
    st.rerun()

# ==========================================
# 4. CONFIGURACIÓN VISUAL (CLÍNICA)
# ==========================================
COLOR_PRIMARIO = "#0A2540" # Azul Marino Institucional
COLOR_SECUNDARIO = "#00A4E4" # Celeste Médico

st.markdown(f"""
<style>
    .stApp {{ background-color: #f8f9fa; }}
    .stContainer {{ background-color: white; border-radius: 8px; padding: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); margin-bottom: 5px; }}
    div[data-testid="metric-container"] {{ background-color: white; border: 1px solid #e0e0e0; padding: 10px; border-radius: 8px; }}
    input[type=number]::-webkit-inner-spin-button {{ -webkit-appearance: none; margin: 0; }}
    .stTabs [data-baseweb="tab"] {{ font-size: 15px; font-weight: bold; }}
    
    /* Botones Corporativos */
    .stButton > button[kind="primary"] {{ background-color: {COLOR_PRIMARIO} !important; border-color: {COLOR_PRIMARIO} !important; color: white !important; font-weight: bold; }}
    .stButton > button[kind="primary"]:hover {{ background-color: {COLOR_SECUNDARIO} !important; border-color: {COLOR_SECUNDARIO} !important; }}
    
    /* Marca Blanca */
    #MainMenu {{ visibility: hidden !important; }} footer {{ display: none !important; }} header {{ display: none !important; }}
</style>
""", unsafe_allow_html=True)

df_precios = cargar_datos()

# ==========================================
# 5. CALCULADORA WINDOWS 
# ==========================================
def mostrar_calculadora_windows():
    calc_html = """
    <!DOCTYPE html><html><head><style>
        body { margin: 0; font-family: sans-serif; background: transparent; }
        .calculator { background: #333; border-radius: 10px; padding: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.3); }
        .display { background: #eee; border-radius: 5px; margin-bottom: 10px; padding: 10px; text-align: right; font-size: 20px; font-weight: bold; color: #333; height: 30px;}
        .grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 5px; }
        button { padding: 10px; border: none; border-radius: 5px; font-size: 14px; font-weight: bold; cursor: pointer; transition: 0.1s; }
        .num { background: #555; color: white; } .num:hover { background: #666; }
        .op { background: #00A4E4; color: white; } .op:hover { background: #0A2540; }
        .clear { background: #a5a5a5; color: black; } .clear:hover { background: #d4d4d4; }
        .eq { background: #0A2540; color: white; grid-column: span 2; } .eq:hover { background: #00A4E4; }
    </style></head><body>
    <div class="calculator"><div class="display" id="disp">0</div><div class="grid">
        <button class="clear" onclick="clr()">C</button><button class="clear" onclick="del()">⌫</button>
        <button class="op" onclick="app('/')">÷</button><button class="op" onclick="app('*')">×</button>
        <button class="num" onclick="app('7')">7</button><button class="num" onclick="app('8')">8</button>
        <button class="num" onclick="app('9')">9</button><button class="op" onclick="app('-')">-</button>
        <button class="num" onclick="app('4')">4</button><button class="num" onclick="app('5')">5</button>
        <button class="num" onclick="app('6')">6</button><button class="op" onclick="app('+')">+</button>
        <button class="num" onclick="app('1')">1</button><button class="num" onclick="app('2')">2</button>
        <button class="num" onclick="app('3')">3</button><button class="num" style="grid-row: span 2;" onclick="app('.')">.</button>
        <button class="num" onclick="app('0')">0</button><button class="eq" onclick="calc()">=</button>
    </div></div>
    <script>
        let d = document.getElementById('disp');
        function app(v){ if(d.innerText=='0')d.innerText=''; d.innerText+=v; }
        function clr(){ d.innerText='0'; }
        function del(){ d.innerText=d.innerText.slice(0,-1)||'0'; }
        function calc(){ try{ d.innerText=eval(d.innerText); }catch{ d.innerText='Error'; } }
    </script></body></html>
    """
    components.html(calc_html, height=280)

# ==========================================
# 6. PDF (LÓGICA EXACTA DE CRISTIAN + SLA)
# ==========================================
class PDF(FPDF):
    def __init__(self, is_official=False, correlativo=""):
        super().__init__()
        self.is_official = is_official
        self.correlativo = correlativo

    def header(self):
        self.set_font('Arial', 'B', 16)
        empresa = "KAUFMANN S.A." if self.is_official else EMPRESA_NOMBRE
        self.cell(0, 10, empresa, 0, 1, 'L')
        self.set_font('Arial', '', 9)
        if not self.is_official:
            self.cell(0, 5, f"RUT: {RUT_EMPRESA}", 0, 1, 'L')
            self.cell(0, 5, f"{DIRECCION} | {TELEFONO}", 0, 1, 'L')
            self.cell(0, 5, EMAIL, 0, 1, 'L')
        else:
            self.cell(0, 5, "Repuestos y Servicio Técnico Mercedes-Benz", 0, 1, 'L')
        
        self.set_xy(130, 10); self.set_font('Arial', 'B', 14)
        if not self.is_official:
            self.set_text_color(255, 255, 255); self.set_fill_color(10, 37, 64) 
            titulo = f"PRESUPUESTO N° {self.correlativo}" if self.correlativo else "PRESUPUESTO"
            self.cell(70, 10, titulo, 1, 1, 'C', 1)
        else:
            self.set_text_color(0, 0, 0)
            titulo = f"COTIZACIÓN N° {self.correlativo}" if self.correlativo else "COTIZACIÓN"
            self.cell(70, 10, titulo, 1, 1, 'C')
            
        self.set_text_color(0, 0, 0)
        self.set_xy(130, 20); self.set_font('Arial', '', 10)
        self.cell(70, 8, f"Fecha Emisión: {datetime.now().strftime('%d/%m/%Y')}", 1, 1, 'C')
        self.ln(15)

    def footer(self):
        self.set_y(-30); self.set_font('Arial', 'I', 8); self.line(10, 265, 200, 265)
        if not self.is_official:
            self.multi_cell(0, 5, "Validez oferta: 15 días. Garantía: 3 meses.", 0, 'C')
        else:
            self.cell(0, 5, "Kaufmann S.A. - Líderes en Movilidad", 0, 1, 'C')

def generar_pdf_exacto(patente, cliente_nombre, marca, modelo, sla, items, total_neto, is_official, correlativo):
    pdf = PDF(is_official=is_official, correlativo=correlativo)
    pdf.add_page(); pdf.set_auto_page_break(auto=True, margin=30) 

    pdf.set_font('Arial', 'B', 10)
    if not is_official: 
        pdf.set_fill_color(0, 164, 228); pdf.set_text_color(255,255,255)
        pdf.cell(0, 6, " IDENTIFICACIÓN DE LA INSTITUCIÓN Y MÓVIL", 1, 1, 'L', 1)
    else: 
        pdf.cell(0, 6, "IDENTIFICACIÓN DEL CLIENTE", 0, 1)
        
    pdf.set_font('Arial', '', 9); pdf.set_text_color(0,0,0)
    nom = cliente_nombre if is_official else cliente_nombre.upper()
    rut = "N/A" if is_official else "92.475.000-6"
    
    pdf.cell(20, 6, "NOMBRE:",0,0); pdf.cell(80, 6, nom,0,0)
    pdf.cell(15, 6, "RUT:",0,0); pdf.cell(0, 6, rut,0,1)
    pdf.ln(5)

    pdf.set_font('Arial', 'B', 10)
    if is_official: pdf.cell(0, 6, "IDENTIFICACIÓN DEL MÓVIL", 0, 1)
    pdf.set_font('Arial', '', 9)

    pdf.cell(20, 6, "PATENTE:",0,0); pdf.cell(40, 6, patente.upper(),0,0)
    pdf.cell(20, 6, "VEHÍCULO:",0,0); pdf.cell(0, 6, f"{marca.upper()} {modelo.upper()}",0,1)
    
    if not is_official and sla:
        pdf.set_font('Arial', 'B', 9)
        pdf.cell(20, 6, "ENTREGA:",0,0); pdf.set_font('Arial', '', 9); pdf.cell(0, 6, str(sla).upper(),0,1)
    pdf.ln(5)
    
    pdf.set_font('Arial', 'B', 9)
    if not is_official: pdf.set_fill_color(10, 37, 64); pdf.set_text_color(255,255,255)
    else: pdf.set_fill_color(240,240,240); pdf.set_text_color(0,0,0)
    
    pdf.cell(100, 8, "Descripción", 1, 0, 'L', 1)
    pdf.cell(15, 8, "Cant.", 1, 0, 'C', 1)
    pdf.cell(35, 8, "Unitario", 1, 0, 'R', 1)
    pdf.cell(35, 8, "Total", 1, 1, 'R', 1)
    pdf.ln(0)
    pdf.set_font('Arial', '', 9); pdf.set_text_color(0,0,0)

    for item in items:
        unit = item['Unitario_Venta'] if is_official else item['Unitario_Costo']
        tot = item['Total_Venta'] if is_official else item['Total_Costo']
        x = pdf.get_x(); y = pdf.get_y()
        pdf.multi_cell(100, 6, item['Descripción'], 1, 'L')
        h = pdf.get_y() - y; pdf.set_xy(x+100, y)
        pdf.cell(15, h, str(item['Cantidad']), 1, 0, 'C')
        pdf.cell(35, h, format_clp(unit), 1, 0, 'R')
        pdf.cell(35, h, format_clp(tot), 1, 0, 'R')
        pdf.set_xy(x, y + h)

    pdf.ln(5)
    iva = total_neto * 0.19; bruto = total_neto + iva
    pdf.set_x(120); pdf.cell(35, 6, "Neto:", 0, 0, 'R'); pdf.cell(35, 6, format_clp(total_neto), 1, 1, 'R'); pdf.ln()
    pdf.set_x(120); pdf.cell(35, 6, "IVA (19%):", 0, 0, 'R'); pdf.cell(35, 6, format_clp(iva), 1, 1, 'R'); pdf.ln()
    pdf.set_font('Arial', 'B', 10); pdf.set_x(120)
    if not is_official: pdf.set_fill_color(230,230,230)
    pdf.cell(35, 8, "TOTAL:", 0, 0, 'R'); pdf.cell(35, 8, format_clp(bruto), 1, 1, 'R', 1 if not is_official else 0)

    pdf.ln(15)
    logo_path = None
    if os.path.exists("logo.png"): logo_path = "logo.png"
    elif os.path.exists("logo.jpg"): logo_path = "logo.jpg"
    if logo_path and not is_official:
        pdf.image(logo_path, x=75, w=60); pdf.ln(5)
    
    fecha = datetime.now().strftime('%d-%m-%Y')
    pdf.cell(0, 6, f"Padre las Casas, {fecha}", 0, 1, 'C'); pdf.ln(5)
    firmante = "KAUFMANN S.A." if is_official else EMPRESA_NOMBRE
    pdf.cell(0, 5, firmante, 0, 1, 'C')

    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 7. INTERFAZ Y SIDEBAR
# ==========================================
with st.sidebar:
    if os.path.exists("mercedes.png"): st.image("mercedes.png", width=60)
    else: st.markdown("# 🚑")
    
    if st.button("🗑️ Reiniciar App", type="primary", use_container_width=True): reset_session()
    
    st.markdown("### 🧮 Calculadora")
    mostrar_calculadora_windows() 
    
    st.divider()
    with st.expander("🔐 Supervisor / Admin"):
        password = st.text_input("Contraseña", type="password")
        is_admin = (password == "kaufmann")
        if is_admin: st.success("Modo Kaufmann Activo")

    st.divider()
    with st.expander("📝 Crear Nuevo Trabajo"):
        st.caption("Agrega un repuesto a la base de datos CSV.")
        nuevo_cat = st.selectbox("Categoría", df_precios['Categoria'].unique())
        nuevo_nombre = st.text_input("Nombre del Trabajo")
        nuevo_costo = st.number_input("Costo Christian ($)", min_value=0, step=5000)
        if st.button("💾 Guardar"):
            if nuevo_nombre and nuevo_costo > 0:
                guardar_nuevo_item(nuevo_cat, nuevo_nombre, nuevo_costo)
                st.success("Guardado. Recargando..."); time.sleep(1); st.rerun()
            else: st.error("Faltan datos")

# --- RECUPERACIÓN DE BORRADORES ---
if 'check_borrador' not in st.session_state:
    st.session_state.check_borrador = True
    borrador_recuperado = cargar_borrador_nube()
    if borrador_recuperado and 'tipo_cliente_confirmado' in borrador_recuperado:
        st.session_state.borrador_pendiente = borrador_recuperado

# HEADER PRINCIPAL
c_logo, c_titulo = st.columns([1, 5])
with c_logo:
    if os.path.exists("logo.png"): st.image("logo.png", width=100)
    else: st.markdown("# ⚕️")
with c_titulo:
    st.title("Sistema de Cotizaciones C.H.")
    if is_admin: st.markdown(f"#### 👤 Supervisor: Gabriel | Modo: <span style='color:#D32F2F;'>**Oficial Kaufmann**</span>", unsafe_allow_html=True)
    else: st.markdown(f"#### 👤 Usuario: {EMPRESA_NOMBRE} | Modo: <span style='color:{COLOR_SECUNDARIO};'>**Proveedor**</span>", unsafe_allow_html=True)

st.markdown("---")

if 'paso_actual' not in st.session_state: st.session_state.paso_actual = 1

# Barra de Progreso
if st.session_state.paso_actual == 1: st.markdown(f"**<span style='color:{COLOR_SECUNDARIO};'>🔵 1. Recepción y Datos</span>** ➔ ⚪ 2. Detalle de Trabajos", unsafe_allow_html=True)
elif st.session_state.paso_actual == 2: st.markdown(f"✅ 1. Recepción y Datos ➔ **<span style='color:{COLOR_SECUNDARIO};'>🔵 2. Detalle de Trabajos</span>**", unsafe_allow_html=True)
st.markdown("---")

# ==========================================
# PASO 1: RECEPCIÓN (DATOS + BUSCADOR CRM)
# ==========================================
if st.session_state.paso_actual == 1:
    if 'borrador_pendiente' in st.session_state:
        st.error(f"⚠️ Tienes una cotización en pausa para la unidad **{st.session_state.borrador_pendiente.get('patente_confirmada', '')}**.")
        ca, cb = st.columns(2)
        if ca.button("✅ Recuperar Trabajo", use_container_width=True):
            for k, v in st.session_state.borrador_pendiente.items(): st.session_state[k] = v
            del st.session_state['borrador_pendiente']; st.rerun()
        if cb.button("🗑️ Descartar", use_container_width=True):
            limpiar_borrador_nube(); del st.session_state['borrador_pendiente']; st.rerun()
        st.markdown("---")

    st.markdown("#### 1. Búsqueda Rápida de Unidad")
    c_b1, c_b2 = st.columns([3, 1])
    pat_search = c_b1.text_input("Ingresar Patente", placeholder="Ej: HX-RP10").upper()
    
    st.markdown("""<style>div[data-testid="column"]:nth-of-type(2) div.stButton > button { margin-top: 28px; }</style>""", unsafe_allow_html=True)
    if c_b2.button("🔍 Buscar en Historial", use_container_width=True):
        if pat_search:
            df_h = obtener_base_datos()
            if not df_h.empty and "Patente" in df_h.columns:
                df_f = df_h[df_h["Patente"].str.upper() == pat_search]
                if not df_f.empty:
                    ult = df_f.iloc[-1]
                    st.session_state.temp_mar = ult.get("Marca", "Mercedes-Benz")
                    st.session_state.temp_mod = ult.get("Modelo", "Sprinter")
                    st.success(f"✅ Unidad encontrada. Registra {len(df_f)} ingresos previos.")
                    st.dataframe(df_f[["Fecha", "Correlativo", "Total"]].tail(3), use_container_width=True, hide_index=True)
                else: st.info("Primera vez que ingresa esta unidad.")
        else: st.warning("Escribe una patente.")

    st.markdown("#### 2. Datos para el Presupuesto")
    tipo_cliente = st.selectbox("Institución:", ("SSAS (Servicio Salud)", "Hospital Temuco"))
    
    c_m1, c_m2 = st.columns(2)
    marca = c_m1.text_input("Marca", value=st.session_state.get('temp_mar', 'Mercedes-Benz'))
    modelo = c_m2.text_input("Modelo", value=st.session_state.get('temp_mod', 'Sprinter'))
    
    sla = st.text_input("Tiempo Estimado de Entrega", placeholder="Ej: 48 Horas...")

    if st.button("🚀 CONTINUAR A REPUESTOS", type="primary", use_container_width=True):
        if not pat_search: st.error("⛔ La Patente es obligatoria.")
        else:
            st.session_state.patente_confirmada = pat_search
            st.session_state.tipo_cliente_confirmado = tipo_cliente
            st.session_state.marca_confirmada = marca
            st.session_state.modelo_confirmado = modelo
            st.session_state.sla_confirmado = sla
            st.session_state.paso_actual = 2
            guardar_borrador_nube()
            st.rerun()

# ==========================================
# PASO 2: TUS PESTAÑAS (CSV)
# ==========================================
elif st.session_state.paso_actual == 2:
    pat_c = st.session_state.patente_confirmada
    tc_c = st.session_state.tipo_cliente_confirmado
    
    c_back, c_title = st.columns([1, 4])
    with c_back: 
        if st.button("⬅️ Volver"): st.session_state.paso_actual = 1; st.rerun()
    with c_title: st.markdown(f"### Unidad: **{pat_c}** | {tc_c}")
    st.markdown("---")
    
    emojis = {"Luces y Exterior": "💡", "Carrocería y Vidrios": "🚐", "Interior Sanitario": "🏥", "Asientos y Tapiz": "💺", "Equipamiento y Radio": "📻", "Cabina y Tablero": "📟", "Camilla": "🚑"}
    categorias = df_precios['Categoria'].unique()
    tabs = st.tabs([f"{emojis.get(c, '🔧')} {c}" for c in categorias] + ["➕ Manual (Temp)"])
    
    seleccion_final = []
    col_c_db = 'Costo_SSAS' if tc_c == "SSAS (Servicio Salud)" else 'Costo_Hosp'
    col_v_db = 'Venta_SSAS' if tc_c == "SSAS (Servicio Salud)" else 'Venta_Hosp'

    for i, cat in enumerate(categorias):
        with tabs[i]:
            df_cat = df_precios[df_precios['Categoria'] == cat]
            for index, row in df_cat.iterrows():
                with st.container(border=True):
                    c1, c2, c3 = st.columns([5, 2, 2])
                    with c1: st.markdown(f"**{row['Trabajo']}**")
                    # Las cantidades persisten al ser asignadas a session_state keys automáticamente
                    with c2: qty = st.number_input("Cantidad", 0, 20, key=f"q_{row['Trabajo']}_{index}", label_visibility="collapsed")
                    with c3:
                        if is_admin: st.caption(f"V: {format_clp(row[col_v_db])}\nC: {format_clp(row[col_c_db])}")
                        else: st.markdown(f"**{format_clp(row[col_c_db])}**")
                    
                    if qty > 0:
                        seleccion_final.append({
                            "Descripción": row['Trabajo'], "Cantidad": qty,
                            "Unitario_Costo": row[col_c_db], "Total_Costo": row[col_c_db]*qty,
                            "Unitario_Venta": row[col_v_db], "Total_Venta": row[col_v_db]*qty
                        })

    with tabs[-1]:
        with st.container(border=True):
            st.subheader("Item Temporal a Medida")
            c1, c2, c3 = st.columns([3, 1, 1])
            d_m = c1.text_input("Descripción", key="q_d_m")
            q_m = c2.number_input("Cant", 0, key="q_q_m")
            p_m = c3.number_input("Precio Unitario", 0, step=5000, key="q_p_m")
            if d_m and q_m > 0 and p_m > 0:
                seleccion_final.append({
                    "Descripción": f"(Extra) {d_m}", "Cantidad": q_m,
                    "Unitario_Costo": p_m, "Total_Costo": p_m*q_m,
                    "Unitario_Venta": p_m*1.35, "Total_Venta": (p_m*1.35)*q_m
                })

    # Guardado silencioso de las cantidades modificadas
    guardar_borrador_nube()

    if seleccion_final:
        st.markdown("---")
        total_costo = sum(x['Total_Costo'] for x in seleccion_final)
        total_venta = sum(x['Total_Venta'] for x in seleccion_final)
        
        st.subheader("📊 Resumen Final")
        
        if is_admin:
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Costo Neto", format_clp(total_costo))
            k2.metric("Venta Neta", format_clp(total_venta))
            iva = total_venta * 0.19
            k3.metric("IVA (19%)", format_clp(iva))
            k4.metric("Total Factura", format_clp(total_venta + iva))
            
            if st.button("📄 EMITIR COTIZACIÓN OFICIAL KAUFMANN", type="primary", use_container_width=True):
                correlativo = obtener_y_registrar_correlativo("Kaufmann S.A.", pat_c, st.session_state.marca_confirmada, st.session_state.modelo_confirmado, st.session_state.sla_confirmado, format_clp(total_venta + iva))
                pdf = generar_pdf_exacto(pat_c, tc_c, st.session_state.marca_confirmada, st.session_state.modelo_confirmado, st.session_state.sla_confirmado, seleccion_final, total_venta, True, correlativo)
                st.download_button("📥 DESCARGAR PDF", pdf, f"Cotizacion_Kaufmann_{pat_c}.pdf", "application/pdf", type="primary", use_container_width=True)
                limpiar_borrador_nube()
        else:
            k1, k2, k3 = st.columns(3)
            k1.metric("Neto", format_clp(total_costo))
            iva = total_costo * 0.19
            k2.metric("IVA (19%)", format_clp(iva))
            k3.metric("TOTAL A PAGAR", format_clp(total_costo + iva))
            
            if 'presupuesto_generado' not in st.session_state:
                if st.button("💾 GENERAR PRESUPUESTO FORMAL", type="primary", use_container_width=True):
                    correlativo = obtener_y_registrar_correlativo(tc_c, pat_c, st.session_state.marca_confirmada, st.session_state.modelo_confirmado, st.session_state.sla_confirmado, format_clp(total_costo + iva))
                    st.session_state['correlativo_temp'] = correlativo
                    
                    pdf_bytes = generar_pdf_exacto(pat_c, tc_c, st.session_state.marca_confirmada, st.session_state.modelo_confirmado, st.session_state.sla_confirmado, seleccion_final, total_costo, False, correlativo)
                    st.session_state['presupuesto_generado'] = {'pdf': pdf_bytes, 'nombre': f"Presupuesto_{pat_c}.pdf"}
                    limpiar_borrador_nube()
                    st.rerun()
            else:
                data = st.session_state['presupuesto_generado']
                st.success(f"✅ Presupuesto N° {st.session_state['correlativo_temp']} emitido.")
                st.download_button("📥 DESCARGAR PDF", data['pdf'], data['nombre'], "application/pdf", type="primary", use_container_width=True)
