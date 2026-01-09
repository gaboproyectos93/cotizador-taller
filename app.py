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
from PIL import Image

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
# 2. LÓGICA DE CORRELATIVOS
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
            correlativo_str = str(numero_actual).zfill(6)
            ahora = datetime.now()
            worksheet_hist.append_row([ahora.strftime("%d/%m/%Y"), ahora.strftime("%H:%M:%S"), correlativo_str, patente, cliente, total])
            return correlativo_str
        except: return "ERR-NUBE"
    else: return "OFFLINE"

# ==========================================
# 3. BASE DE DATOS INTELIGENTE
# ==========================================
LISTA_GENDARMERIA = ["BYRH67", "CGZP59", "CVXV81", "DJDS43", "DRTY89", "DRTY99", "JZPJ79", "CGCR37", "GTBC75", "GXSW72", "GYPT12", "HHBL18", "HHBL19", "HKRL36", "HKRL50", "JBDP22", "JBDP23"]
DB_HOSPITALES = {
    "CWKV42": "HOSPITAL PADRE LAS CASAS", "DLTL67": "SAMU", "FLJW92": "HOSPITAL TOLTEN", "GRCH58": "HOSPITAL LONCOCHE", "GXTD94": "HOSPITAL CUNCO", "GXTD96": "HOSPITAL MIRAFLORES", "HKPH64": "HOSPITAL CUNCO", "HKPH65": "HOSPITAL TOLTEN", "HKPH66": "HOSPITAL GALVARINO", "HKPP33": "HOSPITAL LONCOCHE", "HKPV98": "HOSPITAL LAUTARO", "HKRC82": "HOSPITAL PITRUFQUEN", "HKRC84": "HOSPITAL VILLARRICA", "HKRC85": "SAMU / VILCUN", "HRCH58": "HOSPITAL LONCOCHE", "HXRP10": "HOSPITAL TEMUCO", "HXRP11": "HOSPITAL CARAHUE", "HXRP12": "HOSPITAL CUNCO", "HXRP14": "HOSPITAL LONCOCHE", "HXRP15": "HOSPITAL GALVARINO", "HXRP16": "HOSPITAL CARAHUE", "HXRP18": "HOSPITAL PITRUFQUEN", "HXRP19": "HOSPITAL VILLARRICA", "HXRP20": "HOSPITAL TOLTEN", "HXRP21": "HOSPITAL TEMUCO", "HXRP22": "HOSPITAL VILCUN", "HXRP23": "HOSPITAL TEMUCO", "HXRP24": "HOSPITAL GORBEA", "HXRP26": "HOSPITAL LONCOCHE", "HZGX64": "SAMU", "HZGX65": "HOSPITAL VILLARRICA", "HZGX66": "HOSPITAL PITRUFQUEN", "HZGX70": "HOSPITAL TEMUCO", "JHFX18": "SAMU", "KYWG26": "SAMU", "LPCT51": "HOSPITAL TEMUCO", "LPCT53": "HOSPITAL VILLARRICA", "LZPG72": "HOSPITAL PADRE LAS CASAS", "LZPG73": "HOSPITAL PADRE LAS CASAS", "PPYV76": "HOSPITAL LONCOCHE", "RBFR24": "HOSPITAL CARAHUE", "RBFR25": "HOSPITAL PITRUFQUEN", "RBFR28": "HOSPITAL SAAVEDRA", "RBFR29": "HOSPITAL TOLTEN", "RBFR30": "HOSPITAL VILCUN", "SHLF84": "HOSPITAL TEMUCO", "SHLF85": "HOSPITAL GORBEA", "SYTG24": "HOSPITAL NUEVA IMPERIAL"
}

def limpiar_patente(texto):
    if not texto: return ""
    return re.sub(r'[^A-Z0-9]', '', texto.upper())

def detectar_cliente_automatico(patente_input):
    patente_clean = limpiar_patente(patente_input)
    if patente_clean in LISTA_GENDARMERIA: return "GENDARMERÍA DE CHILE", "Gendarmería de Chile"
    hospital = DB_HOSPITALES.get(patente_clean)
    if hospital:
        tipo = "Hospital Temuco" if "TEMUCO" in hospital else "SSAS (Servicio Salud)"
        return hospital, tipo
    return None, None

DATOS_MAESTROS = """Categoria,Trabajo,Costo_SSAS,Venta_SSAS,Costo_Hosp,Venta_Hosp,Costo_Gend,Venta_Gend
Cabina y Tablero,Reparación circuito eléctrico tablero,180000,252000,189000,264600,215800,291330
Equipamiento y Radio,Cambiar sirena y parlante con accesorios,893700,1161810,600000,780000,895670,1164371
Cabina y Tablero,Reparación eléctrica Balizas/Sirena/Luces,280000,392000,294000,411600,280000,378000
Equipamiento y Radio,Cambiar inversor de corriente (2500W),845000,1098500,887250,1153425,895400,1164020
Luces y Exterior,Cambio foco perimetral,195000,273000,204750,276412.5,212630,287051
Luces y Exterior,Cambio foco escena,195000,273000,204750,276412.5,212630,287051
Luces y Exterior,Cambio foco faenero,74900,108605,78645,114035.25,74900,108605
Luces y Exterior,Cambio baliza barral doble LED,1485700,1931410,1559985,2027980.5,1505300,1956890
Luces y Exterior,Cambio focos iluminación interior (x unidad),68900,99905,72345,104900.25,68600,99470
Luces y Exterior,Instalación focos adicionales LED (Kit Neblineros),0,0,0,0,125500,175700
Seguridad y Calabozos,Reparación sistema tecno vigilancia (Cámaras),0,0,0,0,290000,391500
Luces y Exterior,Instalación alarma advertencia retroceso,0,0,0,0,79300,114985
Climatización y Aire,Cambio control de calefacción,0,0,0,0,145200,203280
Climatización y Aire,Cambiar llave de paso de calefacción,0,0,0,0,95600,138620
Climatización y Aire,Reparación de sistema de calefacción,0,0,0,0,290000,391500
Climatización y Aire,Carga Aire Acondicionado,45000,63000,47250,66150,60000,87000
Climatización y Aire,Cambio de compresor A/C,0,0,0,0,580900,755170
Climatización y Aire,Reparación sistema eléctrico A/C,0,0,0,0,290000,391500
Climatización y Aire,Cambio de presostato sistema A/C,0,0,0,0,145000,203000
Climatización y Aire,Cambiar mangueras de A/C,0,0,0,0,90000,130500
Climatización y Aire,Reparar línea de A/C,0,0,0,0,180000,252000
Climatización y Aire,Radiador de aire acondicionado,0,0,0,0,350000,472500
Climatización y Aire,Cambio filtro deshidratante,0,0,0,0,450000,607500
Climatización y Aire,Cambio válvula de expansión,0,0,0,0,165000,231000
Climatización y Aire,Reparación de evaporador,0,0,0,0,480000,648000
Climatización y Aire,Cambio de evaporador,0,0,0,0,480000,648000
Carrocería y Vidrios,Lámina seguridad transparente parabrisas (4 micras),120000,168000,126000,176400,140000,196000
Carrocería y Vidrios,Lámina seguridad 8 micras color (Ventana Puerta),75000,108750,78750,114187.5,75000,101500
Carrocería y Vidrios,Grabado de patente (Parabrisas/Ventanas/Espejos) x unidad,0,0,0,0,10000,14500
Interior Sanitario,Goma para piso interior cabina (x metro),45000,63000,47250,66150,45000,65250
Asientos y Tapiz,Reparación de tapices de asientos,65000,91000,68250,95550,65000,94250
Asientos y Tapiz,Cambio tapices asientos cabina y calabozos,130000,182000,136500,191100,130000,182000
Climatización y Aire,Extractores de aire (calabozo),390000,546000,409500,573300,390000,526500
Carrocería y Vidrios,Servicio Ploteo emblemas corporativos (x pieza),60000,84000,63000,88200,65000,94250
Seguridad y Calabozos,Reparación/Acondicionamiento Calabozos (m2),120000,168000,126000,176400,120000,168000
Seguridad y Calabozos,Modificaciones estructuras de móviles (m2),120000,168000,126000,176400,120000,168000
Seguridad y Calabozos,Protecciones metálicas/Mallas (m2),120000,168000,126000,176400,120000,168000
Interior Sanitario,Reparar línea de oxígeno central (x línea),180000,252000,189000,264600,180000,252000
Interior Sanitario,Reparar línea de aspiración paciente (x línea),165000,231000,173250,242550,180000,252000
Asientos y Tapiz,Tapizado de asiento de paramédico,125000,175000,131250,183750,130000,182000
Asientos y Tapiz,Tapizado de asiento longitudinal,90000,130500,94500,137025,130000,182000
Asientos y Tapiz,Cambio de asiento de paramédico,475800,642330,499590,674446.5,495000,668250
Asientos y Tapiz,Cambio de asiento longitudinal,160000,224000,168000,235200,210000,283500
Camilla,Tapizado de colchoneta de camilla,120000,168000,126000,176400,126000,176400
Carrocería y Vidrios,Cambio de vidrio de puerta Corredera lateral,290000,391500,304500,411075,290000,391500
Carrocería y Vidrios,Láminas Seguridad 10 micras (Ventanas),75000,108750,78750,114187.5,75000,108750
Interior Sanitario,Cambio de luces interiores de gabinete sanitario,58000,84100,60900,88305,58000,84100
Interior Sanitario,Cambiar conjunto motor A/C gabinete,765000,994500,803250,1044225,765000,994500
Equipamiento y Radio,Instalar Radio Transmisor Antena y acc.,1143650,1486745,1200832.5,1561082.25,1143650,1486745
Equipamiento y Radio,Cambiar botonera accesorios emergencia,28900,41905,30345,44000.25,28900,41905
Camilla,Cambiar colchoneta de camilla,90000,130500,94500,137025,90000,130500
Camilla,Reparar Camilla (respaldo elevación),345800,466830,363090,490171.5,345800,466830
Camilla,Reparar Camilla (vástagos y pasadores),165765,232071,174053,243675,165765,232071
Camilla,Cambiar 1 Rueda de Camilla,135800,190120,142590,199626,135800,190120
Camilla,Aceitar y lubricar partes articuladas camilla,90000,130500,94500,137025,90000,130500"""

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
            return pd.DataFrame(data)
        except: return pd.read_csv(io.StringIO(DATOS_MAESTROS))
    return pd.read_csv(io.StringIO(DATOS_MAESTROS))

def guardar_nuevo_item(categoria, nombre, costo):
    client = conectar_google_sheets()
    if client:
        try:
            sheet = client.open(NOMBRE_HOJA_GOOGLE).sheet1
            venta_ssas = costo * 1.40; costo_hosp = costo * 1.05; venta_hosp = venta_ssas * 1.05; costo_gend = costo; venta_gend = costo * 1.40 
            sheet.append_row([categoria, nombre, costo, venta_ssas, costo_hosp, venta_hosp, costo_gend, venta_gend])
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

def format_clp(value):
    try: return f"${float(value):,.0f}".replace(",", ".")
    except: return "$0"

def reset_session():
    # Limpiar parámetros URL también
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

st.markdown("""
<style>
    .stTabs [aria-selected="true"] { background-color: #0054a6 !important; color: white !important; }
    .stTabs [data-baseweb="tab"] { background-color: #f0f2f6; color: #31333F; }
    .stContainer { border: 1px solid rgba(128, 128, 128, 0.2); border-radius: 8px; padding: 10px; margin-bottom: 5px; }
    div[data-testid="stNumberInput"] input { max-width: 100px; text-align: center; }
    input[type=number]::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
    .big-font { font-size:20px !important; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

df_precios = cargar_datos()

# ==========================================
# 6. CALCULADORA (MODAL)
# ==========================================
@st.dialog("🧮 Calculadora Rápida")
def abrir_calculadora():
    calc_html = """<!DOCTYPE html><html><head><style>
        body { margin: 0; font-family: sans-serif; background: transparent; }
        .calculator { background: #2d2d2d; border-radius: 10px; padding: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.3); border: 1px solid #444; }
        .display { background: #eee; border-radius: 5px; margin-bottom: 10px; padding: 10px; text-align: right; font-size: 20px; font-weight: bold; color: #333; height: 30px;}
        .grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 5px; }
        button { padding: 10px; border: none; border-radius: 5px; font-size: 14px; font-weight: bold; cursor: pointer; transition: 0.1s; }
        .num { background: #555; color: white; } .num:hover { background: #666; }
        .op { background: #ff9f0a; color: white; } .op:hover { background: #ffb03b; }
        .clear { background: #a5a5a5; color: black; } .clear:hover { background: #d4d4d4; }
        .eq { background: #007aff; color: white; grid-column: span 2; } .eq:hover { background: #006ce6; }
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
        function app(v){ if(d.innerText=='0')d.innerText=''; d.innerText+=v; }
        function clr(){ d.innerText='0'; }
        function del(){ d.innerText=d.innerText.slice(0,-1)||'0'; }
        function calc(){ try{ d.innerText=eval(d.innerText); }catch{ d.innerText='Error'; } }
    </script></body></html>"""
    components.html(calc_html, height=280)

# ==========================================
# 7. PDF
# ==========================================
class PDF(FPDF):
    def __init__(self, logo_header=None, correlativo=""):
        super().__init__()
        self.logo_header = logo_header
        self.correlativo = correlativo

    def header(self):
        if self.logo_header and os.path.exists(self.logo_header):
            self.image(self.logo_header, x=10, y=8, w=30)
        self.set_xy(45, 10); self.set_font('Arial', 'B', 16)
        empresa = "KAUFMANN S.A." if self.is_official else EMPRESA_NOMBRE
        self.cell(0, 10, empresa, 0, 1, 'L')
        self.set_xy(45, 18); self.set_font('Arial', '', 9)
        if not self.is_official:
            self.cell(0, 5, f"RUT: {RUT_EMPRESA} | {TELEFONO}", 0, 1, 'L')
            self.set_xy(45, 23); self.cell(0, 5, EMAIL, 0, 1, 'L')
        else:
            self.cell(0, 5, "Repuestos y Servicio Técnico Mercedes-Benz", 0, 1, 'L')
        self.set_xy(130, 10); self.set_font('Arial', 'B', 14); self.set_text_color(20, 20, 60)
        titulo = "COTIZACIÓN" if self.is_official else "PRESUPUESTO"
        if self.correlativo and self.correlativo != "BORRADOR": titulo += f" N° {self.correlativo}"
        self.cell(70, 10, titulo, 1, 1, 'C')
        self.set_text_color(0,0,0); self.set_xy(130, 20); self.set_font('Arial', '', 10)
        self.cell(70, 8, f"Fecha: {datetime.now().strftime('%d/%m/%Y')}", 1, 1, 'C'); self.ln(20)

    def footer(self):
        self.set_y(-30); self.set_font('Arial', 'I', 8); self.line(10, 265, 200, 265)
        if not self.is_official:
            legal = "Validez oferta: 15 días. Garantía: 3 meses."
            self.multi_cell(0, 5, legal, 0, 'C')
        else:
            self.cell(0, 5, "Kaufmann S.A. - Líderes en Movilidad", 0, 1, 'C')

def generar_pdf_exacto(patente, modelo, cliente_nombre, items, total_neto, is_official, watermark_file, estado_trabajo, usuario_final_txt, observaciones, correlativo, fotos_adjuntas):
    pdf = PDF(logo_header=watermark_file, correlativo=correlativo)
    pdf.is_official = is_official 
    pdf.add_page(); pdf.set_auto_page_break(auto=True, margin=30) 
    
    pdf.set_font('Arial', 'B', 10); pdf.cell(0, 6, "IDENTIFICACIÓN DEL CLIENTE", 0, 1)
    pdf.set_font('Arial', '', 9)
    nom = "KAUFMANN S.A." if not is_official else cliente_nombre
    rut = "92.475.000-6" if not is_official else "N/A"
    pdf.cell(20, 6, "NOMBRE:",0,0); pdf.cell(80, 6, nom,0,0)
    pdf.cell(15, 6, "RUT:",0,0); pdf.cell(0, 6, rut,0,1)
    if not is_official:
        pdf.set_font('Arial', 'B', 9); pdf.cell(30, 6, "USUARIO FINAL:", 0, 0)
        pdf.set_font('Arial', '', 9); pdf.cell(0, 6, usuario_final_txt, 0, 1) 
    else: pdf.ln(6)
    pdf.ln(2)

    pdf.set_font('Arial', 'B', 10); pdf.cell(0, 6, "IDENTIFICACIÓN DEL MÓVIL", 0, 1)
    pdf.set_font('Arial', '', 9)
    pdf.cell(20, 6, "PATENTE:",0,0); pdf.cell(40, 6, patente,0,0)
    pdf.cell(20, 6, "MODELO:",0,0); pdf.cell(40, 6, modelo, 0, 0)
    pdf.cell(20, 6, "ESTADO:",0,0); pdf.set_font('Arial', '', 9); pdf.cell(0, 6, estado_trabajo, 0, 1)
    pdf.ln(8)
    
    pdf.set_font('Arial', 'B', 9); pdf.set_fill_color(30, 45, 80); pdf.set_text_color(255,255,255)
    pdf.cell(100, 8, "Descripción", 1, 0, 'L', 1)
    pdf.cell(15, 8, "Cant.", 1, 0, 'C', 1)
    pdf.cell(35, 8, "Unitario", 1, 0, 'R', 1)
    pdf.cell(35, 8, "Total", 1, 1, 'R', 1)
    pdf.ln()
    pdf.set_text_color(0,0,0); pdf.set_font('Arial', '', 9)

    for item in items:
        unit = item['Unitario_Venta'] if is_official else item['Unitario_Costo']
        tot = item['Total_Venta'] if is_official else item['Total_Costo']
        x = pdf.get_x(); y = pdf.get_y()
        pdf.multi_cell(100, 6, item['Descripción'], 1, 'L')
        h = pdf.get_y() - y
        pdf.set_xy(x+100, y)
        pdf.cell(15, h, str(item['Cantidad']), 1, 0, 'C')
        pdf.cell(35, h, format_clp(unit), 1, 0, 'R')
        pdf.cell(35, h, format_clp(tot), 1, 0, 'R')
        pdf.set_xy(x, y + h)

    pdf.ln(5)
    iva = total_neto * 0.19; bruto = total_neto + iva
    pdf.set_x(125); pdf.cell(35, 6, "Neto:", 0, 0, 'R'); pdf.cell(35, 6, format_clp(total_neto), 1, 1, 'R'); pdf.ln()
    pdf.set_x(125); pdf.cell(35, 6, "IVA (19%):", 0, 0, 'R'); pdf.cell(35, 6, format_clp(iva), 1, 1, 'R'); pdf.ln()
    pdf.set_font('Arial', 'B', 10); pdf.set_x(125); pdf.set_text_color(20, 20, 60)
    pdf.cell(35, 8, "TOTAL:", 0, 0, 'R'); pdf.cell(35, 8, format_clp(bruto), 1, 1, 'R')
    pdf.set_text_color(0,0,0)

    if observaciones:
        pdf.ln(8); pdf.set_font('Arial', 'B', 9); pdf.cell(0, 6, "OBSERVACIONES / NOTAS:", 0, 1)
        pdf.set_font('Arial', '', 9); pdf.multi_cell(0, 5, observaciones, 0, 'L')

    pdf.ln(10)
    logo_footer = encontrar_imagen("logo") 
    if logo_footer and not is_official: pdf.image(logo_footer, x=75, w=60)
    
    fecha = datetime.now().strftime('%d-%m-%Y')
    pdf.ln(5); pdf.cell(0, 6, f"Padre las Casas, {fecha}", 0, 1, 'C')
    firmante = "KAUFMANN S.A." if is_official else EMPRESA_NOMBRE
    pdf.ln(5); pdf.cell(0, 5, firmante, 0, 1, 'C')

    if fotos_adjuntas:
        pdf.add_page(); pdf.set_font('Arial', 'B', 14); pdf.set_text_color(20, 20, 60)
        pdf.cell(0, 10, "REGISTRO FOTOGRÁFICO", 0, 1, 'C'); pdf.ln(5)
        for i, foto_uploaded in enumerate(fotos_adjuntas):
            try:
                img = Image.open(foto_uploaded).convert('RGB')
                if img.width > 1000:
                    ratio = 1000 / img.width
                    img = img.resize((1000, int(img.height * ratio)))
                temp_filename = f"temp_img_{i}.jpg"
                img.save(temp_filename, quality=50, optimize=True)
                x_pos = (210 - 150) / 2
                if pdf.get_y() > 200: pdf.add_page()
                pdf.image(temp_filename, x=x_pos, w=150); pdf.ln(5)
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

# === GESTIÓN DE PASOS ===
# Verificar si hay parámetros en la URL para restaurar sesión (Anti-Reinicio)
if 'paso_actual' not in st.session_state:
    params = st.query_params
    if "patente" in params and "paso" in params:
        st.session_state.paso_actual = int(params["paso"])
        st.session_state.patente_confirmada = params["patente"]
        st.session_state.tipo_cliente_confirmado = params.get("cliente", "Cliente Particular")
        # Restaurar usuario
        u_auto, t_auto = detectar_cliente_automatico(st.session_state.patente_confirmada)
        st.session_state.usuario_final_confirmado = u_auto if u_auto else "HOSPITAL [ESPECIFICAR]"
    else:
        st.session_state.paso_actual = 1

# --- PASO 1: BIENVENIDA Y PATENTE ---
if st.session_state.paso_actual == 1:
    col_centro = st.columns([1, 2, 1])
    with col_centro[1]:
        logo_main = encontrar_imagen("logo")
        if logo_main: st.image(logo_main, width=200)
        st.title("Cotizador Taller")
        st.markdown("#### 1. Identificación del Vehículo")
        
        patente = st.text_input("Ingrese Patente", placeholder="Ej: HX-RP10", key="input_patente_inicio").upper()
        
        # Lógica de detección en vivo
        auto_index = 0
        usuario_detectado = None
        if patente:
            usuario, tipo = detectar_cliente_automatico(patente)
            if usuario:
                st.success(f"✅ Vehículo reconocido: {usuario}")
                usuario_detectado = usuario
                if tipo == "SSAS (Servicio Salud)": auto_index = 1
                elif tipo == "Hospital Temuco": auto_index = 2
                elif tipo == "Gendarmería de Chile": auto_index = 3
                elif tipo == "Cliente Particular": auto_index = 4
            else:
                st.warning("⚠️ Patente no registrada. Seleccione institución manualmente.")
        
        opciones_cliente = (
            "--- Seleccione Institución ---",
            "SSAS (Servicio Salud)", 
            "Hospital Temuco", 
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
                # GUARDAR Y AVANZAR (Persistencia URL)
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
                st.rerun()

# --- PASO 2: COTIZADOR COMPLETO ---
elif st.session_state.paso_actual == 2:
    tipo_cliente = st.session_state.tipo_cliente_confirmado
    patente_input = st.session_state.patente_confirmada
    
    c1, c2, c3 = st.columns([1, 4, 1])
    with c1: 
        if st.button("⬅️ Volver"): 
            st.query_params.clear() # Limpiar URL al volver
            st.session_state.paso_actual = 1
            st.rerun()
    with c2: st.markdown(f"### 🚗 Cotizando: **{patente_input}** ({tipo_cliente})")
    
    watermark_file = None; logo_header = None 
    if tipo_cliente == "Gendarmería de Chile": watermark_file = encontrar_imagen("gendarmeria"); logo_header = watermark_file; categorias_a_mostrar = df_precios['Categoria'].unique()
    elif tipo_cliente == "Cliente Particular": watermark_file = None; logo_header = None; categorias_a_mostrar = [] 
    else: watermark_file = encontrar_imagen("ambulancia"); logo_header = watermark_file; categorias_a_mostrar = df_precios['Categoria'].unique()

    usuario_final_txt = st.text_input("Usuario Final / Hospital:", value=st.session_state.usuario_final_confirmado)
    
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
                        st.session_state.lista_particular.append({"Descripción": d_m, "Cantidad": q_m, "Unitario_Costo": p_m, "Total_Costo": p_m*q_m, "Unitario_Venta": p_m*1.35, "Total_Venta": (p_m*1.35)*q_m})
                        st.success("Agregado")
                if st.session_state.lista_particular:
                    st.markdown("#### Ítems Agregados:")
                    df_part = pd.DataFrame(st.session_state.lista_particular)
                    st.table(df_part[["Descripción", "Cantidad", "Unitario_Costo", "Total_Costo"]])
                    if st.button("Limpiar Lista"): st.session_state.lista_particular = []; st.rerun()
                    seleccion_final = st.session_state.lista_particular
    else:
        tabs = st.tabs([f"{emojis.get(c, '🔧')} {c}" for c in categorias_a_mostrar] + ["➕ Manual (Temp)"])
        if tipo_cliente == "SSAS (Servicio Salud)": col_c_db = 'Costo_SSAS'; col_v_db = 'Venta_SSAS'
        elif tipo_cliente == "Hospital Temuco": col_c_db = 'Costo_Hosp'; col_v_db = 'Venta_Hosp'
        else: col_c_db = 'Costo_Gend'; col_v_db = 'Venta_Gend'

        for i, cat in enumerate(categorias_a_mostrar):
            with tabs[i]:
                df_cat = df_precios[df_precios['Categoria'] == cat]
                items_validos = df_cat[df_cat[col_c_db] > 0]
                if items_validos.empty: st.info("⚠️ Esta categoría no aplica para el cliente seleccionado.")
                else:
                    for index, row in items_validos.iterrows():
                        with st.container(): 
                            c1, c2 = st.columns([7, 2], vertical_alignment="center")
                            if is_admin: precio_txt = f"V: {format_clp(row[col_v_db])} | C: {format_clp(row[col_c_db])}"
                            else: precio_txt = f"💰 {format_clp(row[col_c_db])}"
                            c1.markdown(f"**{row['Trabajo']}**")
                            c1.caption(precio_txt)
                            key_input = f"q_{row['Trabajo']}_{index}"
                            val = st.session_state.get(key_input, 0)
                            qty = c2.number_input("", 0, 20, value=val, key=key_input, label_visibility="collapsed")
                            if qty > 0:
                                seleccion_final.append({"Descripción": row['Trabajo'], "Cantidad": qty, "Unitario_Costo": row[col_c_db], "Total_Costo": row[col_c_db]*qty, "Unitario_Venta": row[col_v_db], "Total_Venta": row[col_v_db]*qty})

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
                        st.session_state.items_manuales_extra.append({"Descripción": f"(Extra) {d_m}", "Cantidad": q_m, "Unitario_Costo": p_m, "Total_Costo": p_m * q_m, "Unitario_Venta": p_m * 1.35, "Total_Venta": (p_m * 1.35) * q_m})
                        st.success(f"Agregado: {d_m}")
                if st.session_state.items_manuales_extra:
                    st.markdown("---"); st.markdown("###### Ítems Manuales:")
                    for item in st.session_state.items_manuales_extra: st.text(f"• {item['Cantidad']}x {item['Descripción']}")
                    if st.button("Limpiar Manuales"): st.session_state.items_manuales_extra = []; st.rerun()
                    seleccion_final.extend(st.session_state.items_manuales_extra)

    if seleccion_final:
        st.markdown("---")
        total_costo = sum(x['Total_Costo'] for x in seleccion_final)
        total_venta = sum(x['Total_Venta'] for x in seleccion_final)
        st.subheader("📊 Resumen Final")
        if is_admin:
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Costo Neto", format_clp(total_costo))
            k2.metric("Venta Neta", format_clp(total_venta))
            iva = total_venta * 0.19; k3.metric("IVA (19%)", format_clp(iva))
            total_final = total_venta + iva; k4.metric("Total Factura", format_clp(total_final))
        else:
            k1, k2, k3 = st.columns(3)
            k1.metric("Neto", format_clp(total_costo))
            iva = total_costo * 0.19; k2.metric("IVA (19%)", format_clp(iva))
            total_final = total_costo + iva; k3.metric("TOTAL A PAGAR", format_clp(total_final))

        observaciones_txt = st.text_area("Notas / Observaciones:", height=100)
        st.markdown("### 📸 Fotografías (Cámara integrada)")
        
        # WIDGET CÁMARA INTEGRADA (ANTI-REINICIO)
        foto_camara = st.camera_input("Tomar foto con la cámara", label_visibility="collapsed")
        
        st.caption("O subir desde galería:")
        fotos_galeria = st.file_uploader("Subir archivos", accept_multiple_files=True, type=['jpg', 'png', 'jpeg'], label_visibility="collapsed")
        
        # Combinar fotos
        fotos_totales = []
        if foto_camara: fotos_totales.append(foto_camara)
        if fotos_galeria: fotos_totales.extend(fotos_galeria)

        estado_trabajo = st.radio("Estado:", ("En Espera de Aprobación", "Trabajo Realizado"))

        if 'presupuesto_generado' not in st.session_state:
            if st.button("💾 FINALIZAR Y GENERAR PRESUPUESTO", type="primary", use_container_width=True):
                correlativo = obtener_y_registrar_correlativo(patente_input, usuario_final_txt, format_clp(total_final))
                
                if is_admin: pdf_bytes = generar_pdf_exacto(patente_input, "SPRINTER", usuario_final_txt, seleccion_final, total_venta, True, watermark_file, estado_trabajo, usuario_final_txt, observaciones_txt, correlativo, fotos_totales)
                else: pdf_bytes = generar_pdf_exacto(patente_input, "SPRINTER", "Kaufmann S.A.", seleccion_final, total_costo, False, watermark_file, estado_trabajo, usuario_final_txt, observaciones_txt, correlativo, fotos_totales)
                
                st.session_state['presupuesto_generado'] = {'pdf': pdf_bytes, 'nombre': f"Presupuesto {correlativo} - {patente_input}.pdf"}
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