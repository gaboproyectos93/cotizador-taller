import streamlit as st
import pandas as pd
import io
import os
import base64
import streamlit.components.v1 as components
from fpdf import FPDF
from datetime import datetime
import time
import gspread
import re
from oauth2client.service_account import ServiceAccountCredentials
from PIL import Image, ImageOps
import json

# ==========================================
# 1. CONFIGURACIÓN Y CONEXIÓN
# ==========================================
st.set_page_config(page_title="Cotizador C.H. Servicio Automotriz", layout="wide", page_icon="🚘")

NOMBRE_HOJA_GOOGLE = "DB_Cotizador"

def conectar_google_sheets():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    try:
        if "gcp_service_account" in st.secrets:
            creds_dict = st.secrets["gcp_service_account"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        elif os.path.exists('credentials.json'):
            creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        else: return None
        client = gspread.authorize(creds)
        return client 
    except: return None

# ==========================================
# 2. LÓGICA DE CORRELATIVOS Y BORRADOR
# ==========================================
def obtener_y_registrar_correlativo(patente, cliente, total):
    client = conectar_google_sheets()
    if client:
        try:
            spreadsheet = client.open(NOMBRE_HOJA_GOOGLE)
            try: worksheet_hist = spreadsheet.worksheet("Historial")
            except:
                worksheet_hist = spreadsheet.add_worksheet(title="Historial", rows="1000", cols="6")
                worksheet_hist.append_row(["Fecha", "Hora", "Correlativo", "Patente", "Cliente", "Monto Total"])
            
            datos = worksheet_hist.get_all_values()
            numero_actual = len(datos) 
            correlativo_str = str(numero_actual) # SIN RELLENO DE CEROS
            ahora = datetime.now()
            worksheet_hist.append_row([ahora.strftime("%d/%m/%Y"), ahora.strftime("%H:%M:%S"), correlativo_str, patente, cliente, total])
            return correlativo_str
        except: return "ERR-NUBE"
    else: return "OFFLINE"

def guardar_borrador_nube():
    client = conectar_google_sheets()
    if not client: return
    try:
        sheet = client.open(NOMBRE_HOJA_GOOGLE)
        try: ws = sheet.worksheet("Borrador")
        except: ws = sheet.add_worksheet(title="Borrador", rows="2", cols="2")
        keys_to_save = ['paso_actual', 'lista_particular', 'items_manuales_extra']
        datos = {k: v for k, v in st.session_state.items() if k.endswith('_confirmado') or k.endswith('_confirmada') or k in keys_to_save or k.startswith('q_')}
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
# 3. BASE DE DATOS INTELIGENTE
# ==========================================
def limpiar_patente(texto):
    if not texto: return ""
    return re.sub(r'[^A-Z0-9]', '', texto.upper())

@st.cache_data(ttl=3600)
def cargar_base_vehiculos():
    base_por_defecto = {
        "--- Seleccione Marca ---": ["---"],
        "Mercedes-Benz": ["Sprinter", "Vito", "Citan", "Clase A", "Clase C", "GLA", "GLC", "GLE"],
        "Especiales / Conversiones": ["Carro de Arrastre", "Clínica Móvil", "Conversión a Ambulancia", "Oficina Móvil", "Remolque Especial"],
        "Chevrolet": ["Sail", "Spark", "Tracker", "Colorado", "Silverado", "D-Max", "Captiva", "Onix", "Groove", "Spin", "N300", "Optra"],
        "Toyota": ["Yaris", "Hilux", "RAV4", "Corolla", "Auris", "4Runner", "Fortuner", "Land Cruiser", "Prius", "Rush", "Urban Cruiser"],
        "Hyundai": ["Accent", "Tucson", "Santa Fe", "Elantra", "Creta", "Grand i10", "H-1", "Porter", "Venue", "Kona", "Ioniq"],
        "Kia": ["Morning", "Rio", "Cerato", "Sportage", "Sorento", "Frontier", "Soluto", "Sonet", "Niro", "Carnival", "Carens"],
        "Nissan": ["Versa", "Sentra", "Qashqai", "X-Trail", "NP300", "Navara", "Kicks", "March", "Pathfinder", "Terrano", "Tiida"],
        "Suzuki": ["Swift", "Baleno", "Vitara", "Grand Nomade", "Jimny", "Dzire", "S-Presso", "Ertiga", "Celerio", "Alto", "S-Cross"],
        "Peugeot": ["208", "2008", "308", "3008", "5008", "Partner", "Boxer", "Expert", "Rifter"],
        "Ford": ["Ranger", "F-150", "Territory", "Escape", "Explorer", "Edge", "Transit", "Ecosport", "Puma"]
    }
    try:
        if os.path.exists("vehiculos.csv"):
            df = pd.read_csv("vehiculos.csv", encoding='utf-8')
            if 'Marca' in df.columns and 'Modelo' in df.columns:
                base_csv = {"--- Seleccione Marca ---": ["---"]}
                base_csv["Especiales / Conversiones"] = ["Carro de Arrastre", "Clínica Móvil", "Conversión a Ambulancia", "Oficina Móvil", "Remolque Especial"]
                marcas = sorted([str(m) for m in df['Marca'].dropna().unique()])
                for marca in marcas:
                    if marca not in base_csv:
                        modelos = df[df['Marca'] == marca]['Modelo'].dropna().tolist()
                        base_csv[marca] = sorted(list(set([str(m) for m in modelos])))
                return base_csv
    except Exception as e:
        pass 
    return base_por_defecto

BASE_VEHICULOS = cargar_base_vehiculos()

@st.cache_data(ttl=60)
def cargar_directorio_patentes():
    client = conectar_google_sheets()
    
    default_gend = [["BYRH67", "GENDARMERÍA DE CHILE"], ["CGZP59", "GENDARMERÍA DE CHILE"], ["CVXV81", "GENDARMERÍA DE CHILE"], ["DJDS43", "GENDARMERÍA DE CHILE"], ["DRTY89", "GENDARMERÍA DE CHILE"], ["DRTY99", "GENDARMERÍA DE CHILE"], ["JZPJ79", "GENDARMERÍA DE CHILE"], ["CGCR37", "GENDARMERÍA DE CHILE"], ["GTBC75", "GENDARMERÍA DE CHILE"], ["GXSW72", "GENDARMERÍA DE CHILE"], ["GYPT12", "GENDARMERÍA DE CHILE"], ["HHBL18", "GENDARMERÍA DE CHILE"], ["HHBL19", "GENDARMERÍA DE CHILE"], ["HKRL36", "GENDARMERÍA DE CHILE"], ["HKRL50", "GENDARMERÍA DE CHILE"], ["JBDP22", "GENDARMERÍA DE CHILE"], ["JBDP23", "GENDARMERÍA DE CHILE"]]
    
    default_hosp = {
        "CWKV42": "HOSPITAL PADRE LAS CASAS", "DLTL67": "SAMU", "FLJW92": "HOSPITAL TOLTEN", "GRCH58": "HOSPITAL LONCOCHE", "GXTD94": "HOSPITAL CUNCO", "GXTD96": "HOSPITAL MIRAFLORES", "HKPH64": "HOSPITAL CUNCO", "HKPH65": "HOSPITAL TOLTEN", "HKPH66": "HOSPITAL GALVARINO", "HKPP33": "HOSPITAL LONCOCHE", "HKPV98": "HOSPITAL LAUTARO", "HKRC82": "HOSPITAL PITRUFQUEN", "HKRC84": "HOSPITAL VILLARRICA", "HKRC85": "SAMU / VILCUN", "HRCH58": "HOSPITAL LONCOCHE", "HXRP10": "HOSPITAL TEMUCO", "HXRP11": "HOSPITAL CARAHUE", "HXRP12": "HOSPITAL CUNCO", "HXRP14": "HOSPITAL LONCOCHE", "HXRP15": "HOSPITAL GALVARINO", "HXRP16": "HOSPITAL CARAHUE", "HXRP18": "HOSPITAL PITRUFQUEN", "HXRP19": "HOSPITAL VILLARRICA", "HXRP20": "HOSPITAL TOLTEN", "HXRP21": "HOSPITAL TEMUCO", "HXRP22": "HOSPITAL VILCUN", "HXRP23": "HOSPITAL TEMUCO", "HXRP24": "HOSPITAL GORBEA", "HXRP26": "HOSPITAL LONCOCHE", "HZGX64": "SAMU", "HZGX65": "HOSPITAL VILLARRICA", "HZGX66": "HOSPITAL PITRUFQUEN", "HZGX70": "HOSPITAL TEMUCO", "JHFX18": "SAMU", "KYWG26": "SAMU", "LPCT51": "HOSPITAL TEMUCO", "LPCT53": "HOSPITAL VILLARRICA", "LZPG72": "HOSPITAL PADRE LAS CASAS", "LZPG73": "HOSPITAL PADRE LAS CASAS", "PPYV76": "HOSPITAL LONCOCHE", "RBFR24": "HOSPITAL CARAHUE", "RBFR25": "HOSPITAL PITRUFQUEN", "RBFR28": "HOSPITAL SAAVEDRA", "RBFR29": "HOSPITAL TOLTEN", "RBFR30": "HOSPITAL VILCUN", "SHLF84": "HOSPITAL TEMUCO", "SHLF85": "HOSPITAL GORBEA", "SYTG24": "HOSPITAL NUEVA IMPERIAL"
    }
    
    default_data = default_gend + [[k, v] for k, v in default_hosp.items()]
    df_default = pd.DataFrame(default_data, columns=["Patente", "Institucion"])
    
    if client:
        try:
            sheet = client.open(NOMBRE_HOJA_GOOGLE)
            try: 
                ws = sheet.worksheet("Directorio_Patentes")
                data = ws.get_all_records()
                if data:
                    return pd.DataFrame(data)
            except:
                ws = sheet.add_worksheet(title="Directorio_Patentes", rows="500", cols="2")
                ws.update([df_default.columns.values.tolist()] + df_default.values.tolist())
                return df_default
        except Exception:
            pass
    return df_default

def detectar_cliente_automatico(patente_input):
    patente_clean = limpiar_patente(patente_input)
    if not patente_clean: return None, None
    
    df_patentes = cargar_directorio_patentes()
    match = df_patentes[df_patentes['Patente'].astype(str).str.upper() == patente_clean]
    
    if not match.empty:
        institucion = str(match.iloc[0]['Institucion']).upper()
        if "GENDARMERÍA" in institucion or "GENDARMERIA" in institucion:
            return "GENDARMERÍA DE CHILE", "Gendarmería de Chile"
        elif "TEMUCO" in institucion:
            return institucion, "Hospital Temuco"
        elif "VILLARRICA" in institucion:
            return institucion, "Hospital Villarrica"
        elif "LAUTARO" in institucion:
            return institucion, "Hospital Lautaro"
        elif "PITRUFQUEN" in institucion or "PITRUFQUÉN" in institucion:
            return institucion, "Hospital Pitrufquén"
        else:
            return institucion, "SSAS (Servicio Salud)"
            
    return None, None

DATOS_MAESTROS = """Categoria,Trabajo,Costo_SSAS,Costo_Hosp_Temuco,Costo_Hosp_Villarrica,Costo_Hosp_Lautaro,Costo_Hosp_Pitrufquen,Costo_Gend
Cabina y Tablero,Reparación circuito eléctrico tablero,180000,189000,180000,180000,180000,215800
Equipamiento y Radio,Cambiar sirena y parlante con accesorios,893700,600000,893700,893700,893700,895670
Cabina y Tablero,Reparación eléctrica Balizas/Sirena/Luces,280000,294000,280000,280000,280000,280000
Equipamiento y Radio,Cambiar inversor de corriente (2500W),845000,887250,845000,845000,845000,895400
Luces y Exterior,Cambio foco perimetral,195000,204750,195000,195000,195000,212630
Luces y Exterior,Cambio foco escena,195000,204750,195000,195000,195000,212630
Luces y Exterior,Cambio foco faenero,74900,78645,74900,74900,74900,74900
Luces y Exterior,Cambio baliza barral doble LED,1485700,1559985,1485700,1485700,1485700,1505300
Luces y Exterior,Cambio focos iluminación interior (x unidad),68900,72345,68900,68900,68900,68600
Luces y Exterior,Instalación focos adicionales LED (Kit Neblineros),0,0,0,0,0,125500
Seguridad y Calabozos,Reparación sistema tecno vigilancia (Cámaras),0,0,0,0,0,290000
Luces y Exterior,Instalación alarma advertencia retroceso,0,0,0,0,0,79300
Climatización y Aire,Cambio control de calefacción,0,0,0,0,0,145200
Climatización y Aire,Cambiar llave de paso de calefacción,0,0,0,0,0,95600
Climatización y Aire,Reparación de sistema de calefacción,0,0,0,0,0,290000
Climatización y Aire,Carga Aire Acondicionado,45000,47250,45000,45000,45000,60000
Climatización y Aire,Cambio de compresor A/C,0,0,0,0,0,580900
Climatización y Aire,Reparación sistema eléctrico A/C,0,0,0,0,0,290000
Climatización y Aire,Cambio de presostato sistema A/C,0,0,0,0,0,145000
Climatización y Aire,Cambiar mangueras de A/C,0,0,0,0,0,90000
Climatización y Aire,Reparar línea de A/C,0,0,0,0,0,180000
Climatización y Aire,Radiador de aire acondicionado,0,0,0,0,0,350000
Climatización y Aire,Cambio filtro deshidratante,0,0,0,0,0,450000
Climatización y Aire,Cambio válvula de expansión,0,0,0,0,0,165000
Climatización y Aire,Reparación de evaporador,0,0,0,0,0,480000
Climatización y Aire,Cambio de evaporador,0,0,0,0,0,480000
Carrocería y Vidrios,Lámina seguridad transparente parabrisas (4 micras),120000,126000,120000,120000,120000,140000
Carrocería y Vidrios,Lámina seguridad 8 micras color (Ventana Puerta),75000,78750,75000,75000,75000,75000
Carrocería y Vidrios,Grabado de patente (Parabrisas/Ventanas/Espejos) x unidad,0,0,0,0,0,10000
Interior Sanitario,Goma para piso interior cabina (x metro),45000,47250,45000,45000,45000,45000
Asientos y Tapiz,Reparación de tapices de asientos,65000,68250,65000,65000,65000,65000
Asientos y Tapiz,Cambio tapices asientos cabina y calabozos,130000,136500,130000,130000,130000,130000
Climatización y Aire,Extractores de aire (calabozo),390000,409500,390000,390000,390000,390000
Carrocería y Vidrios,Servicio Ploteo emblemas corporativos (x pieza),60000,63000,60000,60000,60000,65000
Seguridad y Calabozos,Reparación/Acondicionamiento Calabozos (m2),120000,126000,120000,120000,120000,120000
Seguridad y Calabozos,Modificaciones estructuras de móviles (m2),120000,126000,120000,120000,120000,120000
Seguridad y Calabozos,Protecciones metálicas/Mallas (m2),120000,126000,120000,120000,120000,120000
Interior Sanitario,Reparar línea de oxígeno central (x línea),180000,189000,180000,180000,180000,180000
Interior Sanitario,Reparar línea de aspiración paciente (x línea),165000,173250,165000,165000,165000,180000
Asientos y Tapiz,Tapizado de asiento de paramédico,125000,131250,125000,125000,125000,130000
Asientos y Tapiz,Tapizado de asiento longitudinal,90000,94500,90000,90000,90000,130000
Asientos y Tapiz,Cambio de asiento de paramédico,475800,499590,475800,475800,475800,495000
Asientos y Tapiz,Cambio de asiento longitudinal,160000,168000,160000,160000,160000,210000
Camilla,Tapizado de colchoneta de camilla,120000,126000,120000,120000,120000,126000
Carrocería y Vidrios,Cambio de vidrio de puerta Corredera lateral,290000,304500,290000,290000,290000,290000
Carrocería y Vidrios,Láminas Seguridad 10 micras (Ventanas),75000,78750,75000,75000,75000,75000
Interior Sanitario,Cambio de luces interiores de gabinete sanitario,58000,60900,58000,58000,58000,58000
Interior Sanitario,Cambiar conjunto motor A/C gabinete,765000,803250,765000,765000,765000,765000
Equipamiento y Radio,Instalar Radio Transmisor Antena y acc.,1143650,1200832.5,1143650,1143650,1143650,1143650
Equipamiento y Radio,Cambiar botonera accesorios emergencia,28900,30345,28900,28900,28900,28900
Camilla,Cambiar colchoneta de camilla,90000,94500,90000,90000,90000,90000
Camilla,Reparar Camilla (respaldo elevación),345800,363090,345800,345800,345800,345800
Camilla,Reparar Camilla (vástagos y pasadores),165765,174053,165765,165765,165765,165765
Camilla,Cambiar 1 Rueda de Camilla,135800,142590,135800,135800,135800,135800
Camilla,Aceitar y lubricar partes articuladas camilla,90000,94500,90000,90000,90000,90000"""

@st.cache_data(ttl=60)
def cargar_datos():
    client = conectar_google_sheets()
    if client:
        try:
            sheet = client.open(NOMBRE_HOJA_GOOGLE).sheet1
            data = sheet.get_all_records()
            if not data:
                df_init = pd.read_csv(io.StringIO(DATOS_MAESTROS))
                sheet.update([df_init.columns.values.tolist()] + df_init.values.tolist())
                return df_init
            
            df = pd.DataFrame(data)
            cambios_realizados = False
            
            if 'Venta_SSAS' in df.columns:
                df = df.drop(columns=['Venta_SSAS', 'Venta_Hosp', 'Venta_Gend'], errors='ignore')
                cambios_realizados = True
            
            if 'Costo_Hosp' in df.columns:
                df.rename(columns={'Costo_Hosp': 'Costo_Hosp_Temuco'}, inplace=True)
                df['Costo_Hosp_Villarrica'] = df['Costo_SSAS']
                df['Costo_Hosp_Lautaro'] = df['Costo_SSAS']
                df['Costo_Hosp_Pitrufquen'] = df['Costo_SSAS']
                cambios_realizados = True
                
            if cambios_realizados:
                cols = ['Categoria', 'Trabajo', 'Costo_SSAS', 'Costo_Hosp_Temuco', 'Costo_Hosp_Villarrica', 'Costo_Hosp_Lautaro', 'Costo_Hosp_Pitrufquen', 'Costo_Gend']
                df = df[[c for c in cols if c in df.columns]]
                sheet.clear()
                sheet.update([df.columns.values.tolist()] + df.values.tolist())
                
            return df
        except: return pd.read_csv(io.StringIO(DATOS_MAESTROS))
    return pd.read_csv(io.StringIO(DATOS_MAESTROS))

def guardar_nuevo_item(categoria, nombre, costo):
    client = conectar_google_sheets()
    if client:
        try:
            sheet = client.open(NOMBRE_HOJA_GOOGLE).sheet1
            costo_ssas = costo
            costo_hosp_temuco = costo * 1.05
            costo_hosp_villarrica = costo
            costo_hosp_lautaro = costo
            costo_hosp_pitrufquen = costo
            costo_gend = costo
            sheet.append_row([categoria, nombre, costo_ssas, costo_hosp_temuco, costo_hosp_villarrica, costo_hosp_lautaro, costo_hosp_pitrufquen, costo_gend])
            st.cache_data.clear(); return True
        except: return False
    return False

# ==========================================
# 5. UTILS Y ESTILOS
# ==========================================
EMPRESA_NOMBRE = "C.H. SERVICIO AUTOMOTRIZ"
RUT_EMPRESA = "13.961.700-2" 
DIRECCION = "Francisco Pizarro 495, Padre las Casas, Región de la Araucanía"
TELEFONO = "+56 9 8922 0616"
EMAIL = "c.h.servicioautomotriz@gmail.com"

COLOR_PRIMARIO = "#0A2540" 

def format_clp(value):
    try: return f"${float(value):,.0f}".replace(",", ".")
    except: return "$0"

def reset_session():
    limpiar_borrador_nube()
    st.query_params.clear()
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

def encontrar_imagen(nombre_base):
    extensiones = ['.jpg', '.png', '.jpeg', '.JPG', '.PNG']
    for ext in extensiones:
        if os.path.exists(nombre_base + ext): return nombre_base + ext
        if os.path.exists(nombre_base.capitalize() + ext): return nombre_base.capitalize() + ext
    return None

# SE ELIMINÓ TODO EL CSS RÍGIDO DEL CONTENEDOR PARA ARREGLAR EL MODO OSCURO NATIVO
st.markdown(f"""
<style>
    .stTabs [aria-selected="true"] {{ background-color: {COLOR_PRIMARIO} !important; color: white !important; border-radius: 4px 4px 0px 0px; }}
    div[data-testid="stNumberInput"] input {{ max-width: 100px; text-align: center; }}
    input[type=number]::-webkit-inner-spin-button {{ -webkit-appearance: none; margin: 0; }}
    .stButton > button[kind="primary"] {{ background-color: {COLOR_PRIMARIO} !important; border-color: {COLOR_PRIMARIO} !important; color: white !important; font-weight: bold; }}
    .stButton > button[kind="primary"]:hover {{ opacity: 0.8; }}
    div[data-baseweb="select"] input {{ pointer-events: none !important; }}
</style>
""", unsafe_allow_html=True)

df_precios = cargar_datos()

# ==========================================
# 6. CALCULADORA Y PDF 
# ==========================================
@st.dialog("🧮 Calculadora Rápida")
def abrir_calculadora():
    calc_html = f"""<!DOCTYPE html><html><head><style>
        body {{ margin: 0; font-family: sans-serif; background: transparent; }}
        .calculator {{ background: #2d2d2d; border-radius: 10px; padding: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.3); border: 1px solid #444; }}
        .display {{ background: #eee; border-radius: 5px; margin-bottom: 10px; padding: 10px; text-align: right; font-size: 20px; font-weight: bold; color: #333; height: 30px;}}
        .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 5px; }}
        button {{ padding: 10px; border: none; border-radius: 5px; font-size: 14px; font-weight: bold; cursor: pointer; transition: 0.1s; }}
        .num {{ background: #555; color: white; }} .num:hover {{ background: #666; }}
        .op {{ background: #eee; color: black; }} .op:hover {{ background: #d4d4d4; }}
        .clear {{ background: #a5a5a5; color: black; }} .clear:hover {{ background: #d4d4d4; }}
        .eq {{ background: {COLOR_PRIMARIO}; color: white; grid-column: span 2; }} .eq:hover {{ opacity: 0.8; }}
    </style></head><body>
    <div class="calculator"><div class="display" id="disp">0</div><div class="grid">
        <button class="clear" onclick="clr()">C</button><button class="clear" onclick="del()">⌫</button><button class="op" onclick="app('/')">÷</button><button class="op" onclick="app('*')">×</button>
        <button class="num" onclick="app('7')">7</button><button class="num" onclick="app('8')">8</button><button class="num" onclick="app('9')">9</button><button class="op" onclick="app('-')">-</button>
        <button class="num" onclick="app('4')">4</button><button class="num" onclick="app('5')">5</button><button class="num" onclick="app('6')">6</button><button class="op" onclick="app('+')">+</button>
        <button class="num" onclick="app('1')">1</button><button class="num" onclick="app('2')">2</button><button class="num" onclick="app('3')">3</button><button class="num" style="grid-row: span 2;" onclick="app('.')">.</button>
        <button class="num" onclick="app('0')">0</button><button class="eq" onclick="calc()">=</button>
    </div></div>
    <script>
        let d = document.getElementById('disp');
        function app(v){{ if(d.innerText=='0')d.innerText=''; d.innerText+=v; }}
        function clr(){{ d.innerText='0'; }}
        function del(){{ d.innerText=d.innerText.slice(0,-1)||'0'; }}
        function calc(){{ try{{ d.innerText=eval(d.innerText); }}catch{{ d.innerText='Error'; }} }}
    </script></body></html>"""
    components.html(calc_html, height=280)

class PDF(FPDF):
    def __init__(self, logo_header=None, correlativo=""):
        super().__init__()
        self.logo_header = logo_header
        self.correlativo = correlativo

    def header(self):
        logo_path = encontrar_imagen("logo")
        
        # --- LÓGICA DE ENCABEZADO CORREGIDA ---
        if not self.is_official and logo_path and os.path.exists(logo_path):
            # Si hay logo y NO es oficial, dibujamos el logo en la izquierda (ancho grande) y OMITIMOS el texto duplicado
            self.image(logo_path, x=10, y=8, w=90)
        else:
            # Si es oficial o no hay logo, escribimos el texto a la izquierda
            if self.logo_header and os.path.exists(self.logo_header):
                self.image(self.logo_header, x=10, y=8, w=30)
                self.set_xy(45, 10)
            else:
                self.set_xy(10, 10)
                
            self.set_font('Arial', 'B', 16)
            empresa = "KAUFMANN S.A." if self.is_official else EMPRESA_NOMBRE
            self.cell(0, 10, empresa, 0, 1, 'L')
            
            self.set_x(45 if self.logo_header else 10)
            self.set_font('Arial', '', 9)
            if not self.is_official:
                self.cell(0, 5, f"RUT: {RUT_EMPRESA} | {TELEFONO}", 0, 1, 'L')
                self.set_x(45 if self.logo_header else 10)
                self.cell(0, 5, EMAIL, 0, 1, 'L')
            else:
                self.cell(0, 5, "Repuestos y Servicio Técnico Mercedes-Benz", 0, 1, 'L')
        
        # --- CAJA DE CORRELATIVO ROJA ---
        self.set_xy(130, 10)
        self.set_text_color(220, 0, 0) 
        self.set_draw_color(220, 0, 0)
        self.set_line_width(0.4)
        
        self.set_font('Arial', 'B', 16)
        titulo = "COTIZACIÓN" if self.is_official else "PRESUPUESTO"
        self.cell(70, 10, titulo, 'LTR', 1, 'C') 
        
        self.set_x(130)
        self.set_font('Arial', 'B', 14)
        correlativo_txt = f"N° {self.correlativo}" if self.correlativo and self.correlativo != "BORRADOR" else "N° BORRADOR"
        self.cell(70, 10, correlativo_txt, 'LBR', 1, 'C')
        
        self.set_text_color(0, 0, 0)
        self.set_draw_color(0, 0, 0)
        self.set_line_width(0.2)
        self.ln(15)

    def footer(self):
        # Footer automático en cada página (Línea + Legal)
        self.set_y(-20)
        self.set_font('Arial', 'I', 8)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(2)
        if not self.is_official:
            legal = DIRECCION + " | Validez oferta: 15 días. Garantía: 3 meses."
            self.multi_cell(0, 4, legal, 0, 'C')
        else:
            self.cell(0, 4, "Kaufmann S.A. - Líderes en Movilidad", 0, 1, 'C')

def generar_pdf_exacto(patente, marca_modelo, cliente_nombre, cliente_rut, items, total_neto, is_official, watermark_file, estado_trabajo, usuario_final_txt, observaciones, correlativo, fotos_adjuntas):
    pdf = PDF(logo_header=watermark_file, correlativo=correlativo)
    pdf.is_official = is_official 
    pdf.add_page(); pdf.set_auto_page_break(auto=True, margin=30) 
    
    def fila_dinamica(lbl1, val1, lbl2, val2, is_last=False):
        start_y = pdf.get_y()
        pdf.set_font('Arial', 'B', 9); pdf.set_xy(10, start_y); pdf.cell(25, 6, lbl1, 0, 0, 'L')
        pdf.set_font('Arial', '', 9); pdf.set_xy(35, start_y); pdf.multi_cell(70, 6, f": {val1}", 0, 'L')
        y_left = pdf.get_y()
        
        y_right = start_y
        if lbl2:
            pdf.set_font('Arial', 'B', 9); pdf.set_xy(105, start_y); pdf.cell(30, 6, lbl2, 0, 0, 'L')
            pdf.set_font('Arial', '', 9); pdf.set_xy(135, start_y); pdf.multi_cell(65, 6, f": {val2}", 0, 'L')
            y_right = pdf.get_y()
        
        max_y = max(y_left, y_right, start_y + 6)
        pdf.line(10, start_y, 10, max_y)
        pdf.line(200, start_y, 200, max_y)
        if is_last: pdf.line(10, max_y, 200, max_y)
        pdf.set_xy(10, max_y)

    pdf.set_y(45) 
    pdf.set_font('Arial', 'B', 10)
    pdf.set_fill_color(10, 37, 64) 
    pdf.set_text_color(255, 255, 255)
    pdf.cell(190, 6, "  DATOS DEL CLIENTE", 1, 1, 'L', 1)
    pdf.set_text_color(0, 0, 0)
    
    nom = usuario_final_txt if is_official else cliente_nombre
    rut = "" if is_official else cliente_rut
    us_final = "" if is_official else usuario_final_txt
    
    fila_dinamica(" Señor(es)", str(nom).upper(), " Fecha Emisión", datetime.now().strftime('%d/%m/%Y'))
    
    if not is_official:
        fila_dinamica(" RUT", str(rut).upper(), " Usuario Final", str(us_final).upper(), is_last=True)
    else:
        if rut: fila_dinamica(" RUT", str(rut).upper(), "", "", is_last=True) 
        else: pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)
    
    pdf.set_font('Arial', 'B', 10)
    pdf.set_fill_color(10, 37, 64)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(190, 6, "  DATOS DEL VEHÍCULO", 1, 1, 'L', 1)
    pdf.set_text_color(0, 0, 0)
    
    fila_dinamica(" Marca / Modelo", str(marca_modelo).upper(), " Patente", str(patente).upper())
    fila_dinamica(" Estado", str(estado_trabajo).upper(), "", "", is_last=True)
    pdf.ln(6)

    pdf.set_font('Arial', 'B', 9)
    pdf.set_fill_color(10, 37, 64) 
    pdf.set_text_color(255, 255, 255)
    pdf.cell(115, 7, "Descripción", 1, 0, 'C', 1)
    pdf.cell(15, 7, "Cant.", 1, 0, 'C', 1)
    pdf.cell(30, 7, "Unitario", 1, 0, 'C', 1)
    pdf.cell(30, 7, "Total", 1, 1, 'C', 1)
    pdf.set_text_color(0, 0, 0) 
    
    pdf.set_font('Arial', '', 9)
    for item in items:
        unit = item['Unitario_Costo']
        tot = item['Total_Costo']
        x = pdf.get_x(); y = pdf.get_y()
        pdf.multi_cell(115, 6, item['Descripción'].upper(), 1, 'L')
        h = pdf.get_y() - y
        pdf.set_xy(x+115, y)
        pdf.cell(15, h, str(item['Cantidad']), 1, 0, 'C')
        pdf.cell(30, h, format_clp(unit), 1, 0, 'R')
        pdf.cell(30, h, format_clp(tot), 1, 1, 'R')
        pdf.set_xy(x, y + h)

    pdf.ln(5)
    iva = total_neto * 0.19; bruto = total_neto + iva
    
    totals_width = 60 
    safe_margin_right = 200 - totals_width
    pdf.set_x(safe_margin_right)
    
    pdf.set_font('Arial', 'B', 9)
    pdf.cell(30, 6, "SUB TOTAL", 1, 0, 'L'); pdf.set_font('Arial', '', 9); pdf.cell(30, 6, format_clp(total_neto), 1, 1, 'R')
    pdf.set_x(safe_margin_right)
    pdf.set_font('Arial', 'B', 9); pdf.cell(30, 6, "I.V.A. (19%)", 1, 0, 'L'); pdf.set_font('Arial', '', 9); pdf.cell(30, 6, format_clp(iva), 1, 1, 'R')
    pdf.set_x(safe_margin_right)
    pdf.set_font('Arial', 'B', 10)
    pdf.set_fill_color(10, 37, 64) 
    pdf.set_text_color(255, 255, 255)
    pdf.cell(30, 8, "TOTAL", 1, 0, 'L', 1); pdf.cell(30, 8, format_clp(bruto), 1, 1, 'R', 1)
    pdf.set_text_color(0, 0, 0)

    if observaciones:
        pdf.ln(8); pdf.set_font('Arial', 'B', 9); pdf.cell(0, 6, "OBSERVACIONES / NOTAS:", 0, 1)
        pdf.set_font('Arial', '', 9); pdf.multi_cell(0, 5, observaciones, 0, 'L')

    # --- FIRMA INTELIGENTE (SIN LOGO EXTRA) ---
    if pdf.get_y() > 240:
        pdf.add_page()
    else:
        pdf.ln(15)

    fecha = datetime.now().strftime('%d-%m-%Y')
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 6, f"Padre las Casas, {fecha}", 0, 1, 'C')
    firmante = "KAUFMANN S.A." if is_official else EMPRESA_NOMBRE
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 5, firmante, 0, 1, 'C')

    if fotos_adjuntas:
        pdf.add_page()
        pdf.set_font('Arial', 'B', 14); pdf.set_text_color(20, 20, 60)
        pdf.cell(0, 10, "REGISTRO FOTOGRÁFICO", 0, 1, 'C')
        pdf.ln(5)
        
        margin_x = 15; margin_y = 60
        w_photo = 85; h_photo = 85
        col_gap = 10; row_gap = 10
        
        for i, foto_uploaded in enumerate(fotos_adjuntas):
            if i > 0 and i % 4 == 0:
                pdf.add_page()
                pdf.cell(0, 10, "REGISTRO FOTOGRÁFICO (Cont.)", 0, 1, 'C')
            
            pos_page = i % 4
            row = pos_page // 2; col = pos_page % 2
            x = margin_x + (col * (w_photo + col_gap))
            y = margin_y + (row * (h_photo + row_gap))
            
            try:
                img = Image.open(foto_uploaded)
                img = ImageOps.exif_transpose(img) 
                img = img.convert('RGB')
                img.thumbnail((600, 600))
                temp_filename = f"temp_img_{i}.jpg"
                img.save(temp_filename, quality=60, optimize=True)
                pdf.image(temp_filename, x=x, y=y, w=w_photo, h=h_photo)
                os.remove(temp_filename)
            except: pass

    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 8. UI PRINCIPAL (FLUJO PASO A PASO)
# ==========================================
with st.sidebar:
    logo_mercedes = encontrar_imagen("mercedes")
    if logo_mercedes: st.image(logo_mercedes, width=60)
    else: st.markdown("# 🏎️")
    
    if st.button("🧮 Abrir Calculadora", use_container_width=True):
        abrir_calculadora()
    
    st.markdown("---")
    if st.button("🗑️ Reiniciar Todo", type="primary", use_container_width=True):
        reset_session()
    
    st.divider()
    with st.expander("🔐 Admin"):
        password = st.text_input("Contraseña", type="password")
        is_admin = (password == "kaufmann")
        if is_admin: st.success("Acceso Concedido")

if 'check_borrador' not in st.session_state:
    st.session_state.check_borrador = True
    borrador_recuperado = cargar_borrador_nube()
    if borrador_recuperado and 'patente_confirmada' in borrador_recuperado:
        st.session_state.borrador_pendiente = borrador_recuperado

if 'paso_actual' not in st.session_state:
    params = st.query_params
    if "patente" in params and "paso" in params:
        st.session_state.paso_actual = int(params["paso"])
        st.session_state.patente_confirmada = params["patente"]
        st.session_state.tipo_cliente_confirmado = params.get("cliente", "Cliente Particular")
        u_auto, t_auto = detectar_cliente_automatico(st.session_state.patente_confirmada)
        st.session_state.usuario_final_confirmado = u_auto if u_auto else "HOSPITAL [ESPECIFICAR]"
    else:
        st.session_state.paso_actual = 1

# --- PASO 1: BIENVENIDA Y PATENTE ---
if st.session_state.paso_actual == 1:
    col_centro = st.columns([1, 2, 1])
    with col_centro[1]:
        
        if 'borrador_pendiente' in st.session_state:
            st.error(f"⚠️ ¡ATENCIÓN! Tienes un presupuesto en pausa para la patente **{st.session_state.borrador_pendiente.get('patente_confirmada', '')}**.")
            ca, cb = st.columns(2)
            if ca.button("✅ Recuperar Trabajo", use_container_width=True):
                for k, v in st.session_state.borrador_pendiente.items(): st.session_state[k] = v
                del st.session_state['borrador_pendiente']; st.rerun()
            if cb.button("🗑️ Descartar", use_container_width=True):
                limpiar_borrador_nube(); del st.session_state['borrador_pendiente']; st.rerun()
            st.markdown("---")

        logo_main = encontrar_imagen("logo")
        if logo_main: st.image(logo_main, width=200)
        st.title("Cotizador Taller")
        st.markdown("#### 1. Identificación del Vehículo")
        
        patente = st.text_input("Ingrese Patente", placeholder="Ej: HX-RP10", key="input_patente_inicio").upper()
        
        auto_index = 0
        usuario_detectado = None
        if patente:
            usuario, tipo = detectar_cliente_automatico(patente)
            if usuario:
                st.success(f"✅ Vehículo reconocido: {usuario}")
                usuario_detectado = usuario
                if tipo == "SSAS (Servicio Salud)": auto_index = 1
                elif tipo == "Hospital Temuco": auto_index = 2
                elif tipo == "Hospital Villarrica": auto_index = 3
                elif tipo == "Hospital Lautaro": auto_index = 4
                elif tipo == "Hospital Pitrufquén": auto_index = 5
                elif tipo == "Gendarmería de Chile": auto_index = 6
                elif tipo == "Cliente Particular": auto_index = 7
            else:
                st.warning("⚠️ Patente no registrada en Directorio. Seleccione institución manualmente.")
        
        opciones_cliente = (
            "--- Seleccione Institución ---",
            "SSAS (Servicio Salud)", 
            "Hospital Temuco",
            "Hospital Villarrica",
            "Hospital Lautaro",
            "Hospital Pitrufquén",
            "Gendarmería de Chile", 
            "Cliente Particular"
        )
        
        tipo_cliente = st.selectbox("Institución / Cliente", opciones_cliente, index=auto_index)
        
        if st.button("🚀 COMENZAR COTIZACIÓN", type="primary", use_container_width=True):
            if tipo_cliente == "--- Seleccione Institución ---":
                st.error("⛔ Debe seleccionar una institución válida para continuar.")
            elif not patente:
                st.error("⛔ Debe ingresar una patente.")
            else:
                st.query_params["patente"] = patente
                st.query_params["cliente"] = tipo_cliente
                st.query_params["paso"] = "2"
                
                st.session_state.patente_confirmada = patente
                st.session_state.tipo_cliente_confirmado = tipo_cliente
                if usuario_detectado: st.session_state.usuario_final_confirmado = usuario_detectado
                elif tipo_cliente == "Cliente Particular": st.session_state.usuario_final_confirmado = "CLIENTE PARTICULAR"
                elif tipo_cliente == "Gendarmería de Chile": st.session_state.usuario_final_confirmado = "GENDARMERÍA DE CHILE"
                else: st.session_state.usuario_final_confirmado = "HOSPITAL [ESPECIFICAR]"
                
                st.session_state.paso_actual = 2
                guardar_borrador_nube() 
                st.rerun()

# --- PASO 2: COTIZADOR COMPLETO ---
elif st.session_state.paso_actual == 2:
    tipo_cliente = st.session_state.tipo_cliente_confirmado
    patente_input = st.session_state.patente_confirmada
    
    c1, c2, c3 = st.columns([1, 4, 1])
    with c1: 
        if st.button("⬅️ Volver"): 
            st.query_params.clear() 
            st.session_state.paso_actual = 1
            st.rerun()
    with c2: st.markdown(f"### 🚗 Cotizando: **{patente_input}** ({tipo_cliente})")
    
    watermark_file = None; logo_header = None 
    if tipo_cliente == "Gendarmería de Chile": watermark_file = encontrar_imagen("gendarmeria"); logo_header = watermark_file; categorias_a_mostrar = df_precios['Categoria'].unique()
    elif tipo_cliente == "Cliente Particular": watermark_file = None; logo_header = None; categorias_a_mostrar = [] 
    else: watermark_file = encontrar_imagen("ambulancia"); logo_header = watermark_file; categorias_a_mostrar = df_precios['Categoria'].unique()

    # --- DATOS DEL CLIENTE A FACTURAR ---
    st.markdown("#### 🏢 Datos del Cliente a Facturar")
    c_f1, c_f2, c_f3 = st.columns([2, 1, 2])
    
    if tipo_cliente in ["SSAS (Servicio Salud)", "Hospital Temuco", "Hospital Villarrica", "Hospital Lautaro", "Hospital Pitrufquén", "Gendarmería de Chile"]:
        def_cliente = "KAUFMANN S.A."
        def_rut = "92.475.000-6"
    else:
        def_cliente = ""
        def_rut = ""
        
    cliente_facturar = c_f1.text_input("Señor(es) / Razón Social", value=def_cliente, placeholder="Nombre de quien paga")
    rut_facturar = c_f2.text_input("RUT", value=def_rut, placeholder="Opcional")
    usuario_final_txt = c_f3.text_input("Usuario Final / Hospital", value=st.session_state.usuario_final_confirmado)
    
    # --- SELECTOR DINÁMICO DE VEHÍCULOS ---
    st.markdown("#### 🚙 Datos Específicos del Vehículo")
    c_v1, c_v2, c_v3 = st.columns(3)
    
    lista_marcas = list(BASE_VEHICULOS.keys())
    if "--- AGREGAR OTRA MARCA ---" not in lista_marcas:
        lista_marcas.append("--- AGREGAR OTRA MARCA ---")
        
    default_marca_index = 0
    if tipo_cliente != "Cliente Particular" and "Mercedes-Benz" in lista_marcas:
        default_marca_index = lista_marcas.index("Mercedes-Benz")

    marca_sel = c_v1.selectbox("Marca", lista_marcas, index=default_marca_index, key="v_marca")
    
    if marca_sel == "--- AGREGAR OTRA MARCA ---":
        marca_final = c_v1.text_input("Escriba la Marca:", placeholder="Ej: Motorhome", key="v_marca_man").upper()
        modelos_lista = ["--- AGREGAR OTRO MODELO ---"]
    else:
        marca_final = marca_sel
        modelos_lista = BASE_VEHICULOS.get(marca_sel, ["---"]).copy()
        if "--- AGREGAR OTRO MODELO ---" not in modelos_lista:
            modelos_lista.append("--- AGREGAR OTRO MODELO ---")
    
    default_modelo_index = 0
    if tipo_cliente != "Cliente Particular" and "Sprinter" in modelos_lista:
        default_modelo_index = modelos_lista.index("Sprinter")

    modelo_sel = c_v2.selectbox("Modelo", modelos_lista, index=default_modelo_index, key="v_modelo")
    
    if modelo_sel == "--- AGREGAR OTRO MODELO ---":
        modelo_final = c_v2.text_input("Escriba el Modelo:", placeholder="Ej: Ducato L3H2", key="v_modelo_man").upper()
    else:
        modelo_final = modelo_sel
        
    patente_sel = c_v3.text_input("Patente (Obligatoria)", value=patente_input, placeholder="Ej: ABCD12", key="v_pat")
    st.markdown("---")

    emojis = { "Luces y Exterior": "💡", "Carrocería y Vidrios": "🚐", "Interior Sanitario": "🏥", "Climatización y Aire": "❄️",
        "Asientos y Tapiz": "💺", "Equipamiento y Radio": "📻", "Cabina y Tablero": "📟", "Camilla": "🚑", "Seguridad y Calabozos": "🔒"}

    seleccion_final = []

    if tipo_cliente == "Cliente Particular":
        tabs = st.tabs(["➕ Ingreso Manual"])
        with tabs[0]:
            st.info("ℹ️ Modo Cliente Particular: Ingrese ítems manualmente.")
            with st.container():
                c1, c2, c3 = st.columns([5.5, 1.5, 2], vertical_alignment="center")
                d_m = c1.text_input("Descripción del Trabajo")
                q_m = c2.number_input("Cnt", min_value=0, value=1)
                p_m = c3.number_input("Precio Unitario ($)", min_value=0, step=5000)
                if 'lista_particular' not in st.session_state: st.session_state.lista_particular = []
                if st.button("Agregar Ítem"):
                    if d_m and q_m > 0 and p_m > 0:
                        st.session_state.lista_particular.append({"Descripción": d_m, "Cantidad": q_m, "Unitario_Costo": p_m, "Total_Costo": p_m*q_m})
                        guardar_borrador_nube() 
                        st.success("Agregado")
                if st.session_state.lista_particular:
                    st.markdown("#### Ítems Agregados:")
                    df_part = pd.DataFrame(st.session_state.lista_particular)
                    st.table(df_part[["Descripción", "Cantidad", "Unitario_Costo", "Total_Costo"]])
                    if st.button("Limpiar Lista"): 
                        st.session_state.lista_particular = []
                        guardar_borrador_nube()
                        st.rerun()
                    seleccion_final = st.session_state.lista_particular
    else:
        tabs = st.tabs([f"{emojis.get(c, '🔧')} {c}" for c in categorias_a_mostrar] + ["➕ Manual (Temp)"])
        
        if tipo_cliente == "SSAS (Servicio Salud)": col_c_db = 'Costo_SSAS'
        elif tipo_cliente == "Hospital Temuco": col_c_db = 'Costo_Hosp_Temuco'
        elif tipo_cliente == "Hospital Villarrica": col_c_db = 'Costo_Hosp_Villarrica'
        elif tipo_cliente == "Hospital Lautaro": col_c_db = 'Costo_Hosp_Lautaro'
        elif tipo_cliente == "Hospital Pitrufquén": col_c_db = 'Costo_Hosp_Pitrufquen'
        else: col_c_db = 'Costo_Gend'

        for i, cat in enumerate(categorias_a_mostrar):
            with tabs[i]:
                df_cat = df_precios[df_precios['Categoria'] == cat]
                items_validos = df_cat[df_cat[col_c_db] > 0]
                if items_validos.empty: st.info("⚠️ Esta categoría no aplica para el cliente seleccionado.")
                else:
                    for index, row in items_validos.iterrows():
                        with st.container(): 
                            c1, c2, c3 = st.columns([5.5, 1.5, 2], vertical_alignment="center")
                            with c1: st.markdown(f"**{row['Trabajo']}**")
                            key_input = f"q_{row['Trabajo']}_{index}"
                            val = st.session_state.get(key_input, 0)
                            
                            qty = c2.number_input("", 0, 20, value=val, key=key_input, label_visibility="collapsed", on_change=guardar_borrador_nube)
                            
                            precio_costo = float(row[col_c_db])
                            
                            with c3:
                                st.markdown(f"**{format_clp(precio_costo)}**")
                                
                            if qty > 0:
                                seleccion_final.append({
                                    "Descripción": row['Trabajo'], 
                                    "Cantidad": qty, 
                                    "Unitario_Costo": precio_costo, 
                                    "Total_Costo": precio_costo * qty
                                })

        with tabs[-1]:
            with st.container():
                st.subheader("Item Temporal")
                if 'items_manuales_extra' not in st.session_state: st.session_state.items_manuales_extra = []
                c1, c2, c3 = st.columns([5.5, 1.5, 2], vertical_alignment="center")
                d_m = c1.text_input("Descripción del Trabajo (Manual)")
                q_m = c2.number_input("Cant.", min_value=1, value=1, key="mq")
                p_m = c3.number_input("Precio Unitario ($)", min_value=0, step=5000)
                if st.button("Agregar Ítem Manual"):
                    if d_m and p_m > 0:
                        st.session_state.items_manuales_extra.append({"Descripción": f"(Extra) {d_m}", "Cantidad": q_m, "Unitario_Costo": p_m, "Total_Costo": p_m * q_m})
                        guardar_borrador_nube() 
                        st.success(f"Agregado: {d_m}")
                if st.session_state.items_manuales_extra:
                    st.markdown("---"); st.markdown("###### Ítems Manuales:")
                    for item in st.session_state.items_manuales_extra: st.text(f"• {item['Cantidad']}x {item['Descripción']}")
                    if st.button("Limpiar Manuales"): 
                        st.session_state.items_manuales_extra = []
                        guardar_borrador_nube()
                        st.rerun()
                    seleccion_final.extend(st.session_state.items_manuales_extra)

    if seleccion_final:
        st.markdown("---")
        total_costo = sum(x['Total_Costo'] for x in seleccion_final)
        st.subheader("📊 Resumen Final")
        k1, k2, k3 = st.columns(3)
        k1.metric("Neto", format_clp(total_costo))
        iva = total_costo * 0.19; k2.metric("IVA (19%)", format_clp(iva))
        total_final = total_costo + iva; k3.metric("TOTAL A PAGAR", format_clp(total_final))

        observaciones_txt = st.text_area("Notas / Observaciones:", height=100)
        st.markdown("### 📸 Fotografías")
        fotos_adjuntas = st.file_uploader("Adjuntar evidencia", accept_multiple_files=True, type=['jpg', 'png', 'jpeg'])
        estado_trabajo = st.radio("Estado:", ("En Espera de Aprobación", "Trabajo Realizado"))

        if 'presupuesto_generado' not in st.session_state:
            if st.button("💾 FINALIZAR Y GENERAR PRESUPUESTO", type="primary", use_container_width=True):
                correlativo = obtener_y_registrar_correlativo(patente_sel, usuario_final_txt, format_clp(total_final))
                
                marca_modelo_pdf = f"{marca_final} {modelo_final}".replace("--- Seleccione Marca ---", "").replace("---", "").strip()
                if not marca_modelo_pdf:
                    marca_modelo_pdf = "NO ESPECIFICADO"
                
                if is_admin: 
                    pdf_bytes = generar_pdf_exacto(patente_sel, marca_modelo_pdf, cliente_facturar, rut_facturar, seleccion_final, total_costo, True, watermark_file, estado_trabajo, usuario_final_txt, observaciones_txt, correlativo, fotos_adjuntas)
                else: 
                    pdf_bytes = generar_pdf_exacto(patente_sel, marca_modelo_pdf, cliente_facturar, rut_facturar, seleccion_final, total_costo, False, watermark_file, estado_trabajo, usuario_final_txt, observaciones_txt, correlativo, fotos_adjuntas)
                
                st.session_state['presupuesto_generado'] = {'pdf': pdf_bytes, 'nombre': f"Presupuesto {correlativo} - {patente_sel}.pdf"}
                limpiar_borrador_nube() 
                st.rerun()
        else:
            data = st.session_state['presupuesto_generado']
            st.success(f"✅ Presupuesto N° {data['nombre']} generado correctamente.")
            st.download_button("📥 DESCARGAR PDF", data['pdf'], data['nombre'], "application/pdf", type="primary", use_container_width=True)
            if st.button("🔄 Nueva Cotización", use_container_width=True): reset_session()

    if tipo_cliente != "Cliente Particular":
        st.divider()
        with st.expander("📝 Crear Nuevo Trabajo (Admin)"):
            nuevo_cat = st.selectbox("Categoría", df_precios['Categoria'].unique())
            nuevo_nombre = st.text_input("Nombre del Trabajo")
            nuevo_costo = st.number_input("Costo ($)", min_value=0, step=5000)
            if st.button("💾 Guardar Item"):
                if nuevo_nombre and nuevo_costo > 0:
                    guardar_nuevo_item(nuevo_cat, nuevo_nombre, nuevo_costo)
                    st.success("Guardado."); time.sleep(1); st.rerun()
