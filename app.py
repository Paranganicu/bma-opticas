# ─────────────────────  BMA ÓPTICAS  v2.2  ─────────────────────
"""Streamlit app: gestión de pacientes, ventas y recetas ópticas.
   Ingreso único desde «Registrar venta».  Valida y formatea RUT
   a «12.345.678-5» aun si el usuario escribe solo números.
"""

# === Imports =============================================================
import os, re, uuid, logging, datetime as dt
from io import BytesIO
from typing import Dict, Any

import pandas as pd
import streamlit as st
from html import escape
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import magic                              # «python-magic» en requirements.txt

# === Configuración global ===============================================
st.set_page_config(page_title="BMA Ópticas", page_icon="👓", layout="wide")
logging.basicConfig(filename="app.log",
                    level=logging.INFO,
                    format="%(asctime)s · %(levelname)s · %(message)s")

DATA_PATH       = "Pacientes.xlsx"
COLUMNAS_OPTICA = [
    "OD_SPH","OD_CYL","OD_EJE",
    "OI_SPH","OI_CYL","OI_EJE",
    "DP_Lejos","DP_CERCA","ADD"
]
MIME_EXCEL = {
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
}

# -----------------------------------------------------------------------
#                        Utilidades RUT
# -----------------------------------------------------------------------
RUT_PATTERN = re.compile(r"[0-9kK\.\-]+$")

def _calc_dv(cuerpo: str) -> str:
    """Calcula dígito verificador (cuerpo sin DV)."""
    s, m = 0, 2
    for c in reversed(cuerpo):
        s += int(c) * m
        m = 2 if m == 7 else m + 1
    dv = 11 - (s % 11)
    return {10: "K", 11: "0"}.get(dv, str(dv))

def rut_limpio(rut_raw: str) -> str | None:
    """Convierte entrada libre a «12.345.678-5» o None si es inválido."""
    rut_raw = rut_raw.strip().upper()
    if not RUT_PATTERN.fullmatch(rut_raw):
        return None

    txt = rut_raw.replace(".", "").replace("-", "")
    if len(txt) < 8:                 # 7+cuerpo + DV mínimo
        return None

    cuerpo, dv_in = txt[:-1], txt[-1]
    dv_calc = _calc_dv(cuerpo)
    if dv_in != dv_calc:             # DV incorrecto
        return None

    # Puntos cada 3 dígitos desde la derecha
    cuerpo_pts = f"{int(cuerpo):,}".replace(",", ".")
    return f"{cuerpo_pts}-{dv_calc}"

# -----------------------------------------------------------------------
#                        Otras utilidades
# -----------------------------------------------------------------------

def enmascarar_rut(rut: str) -> str:
    if "-" not in rut:
        return rut
    cuerpo, dv = rut.split("-")
    return f"{cuerpo[:-4]}****-{dv}" if len(cuerpo) > 4 else rut

def es_excel_valido(path: str) -> bool:
    try:
        return magic.from_file(path, mime=True) in MIME_EXCEL
    except Exception as e:
        logging.error(e)
        return False

def capitalizar(nombre: str) -> str:
    return " ".join(w.capitalize() for w in nombre.strip().split())

# -----------------------------------------------------------------------
#                        Carga / guarda DataFrame
# -----------------------------------------------------------------------
@st.cache_data(ttl=900)
def cargar_datos() -> pd.DataFrame:
    if not os.path.exists(DATA_PATH):
        pd.DataFrame().to_excel(DATA_PATH, index=False)
    if not es_excel_valido(DATA_PATH):
        st.error("❌ 'Pacientes.xlsx' no es un Excel válido")
        return pd.DataFrame()

    df = pd.read_excel(DATA_PATH).copy()
    if "Última_visita" in df:
        df["Última_visita"] = pd.to_datetime(df["Última_visita"], errors="coerce")
    if "Valor" in df:
        df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce").fillna(0)
    for col in COLUMNAS_OPTICA:
        if col in df:
            df[col] = df[col].fillna("").astype(str).str.strip()
    return df

def guardar_datos(df: pd.DataFrame):
    try:
        df.to_excel(DATA_PATH, index=False)
    except Exception as e:
        st.warning(f"⚠️ No se pudo guardar en disco: {e}")
        logging.error(e)

# -----------------------------------------------------------------------
#                        PDF Receta
# -----------------------------------------------------------------------

def pdf_receta(p: Dict[str, Any]) -> BytesIO:
    tmp = f"tmp_{uuid.uuid4()}.pdf"
    buf = BytesIO()
    c   = canvas.Canvas(tmp, pagesize=letter)
    c.setTitle(f"Receta {p.get('Nombre', '')}")
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, 750, "BMA Ópticas – Receta")
    c.setFont("Helvetica", 12)
    c.drawString(72, 730, f"Paciente: {escape(p.get('Nombre', ''))}")
    c.drawString(72, 712, f"RUT: {enmascarar_rut(p.get('Rut', ''))}")
    c.drawString(400, 712, dt.datetime.now().strftime("%d/%m/%Y"))

    y = 680
    c.setFont("Helvetica-Bold", 12); c.drawString(72, y, "OD / OI   ESF   CIL   EJE"); y -= 20
    c.setFont("Helvetica", 12)
    c.drawString(72, y, f"OD: {p.get('OD_SPH','')}  {p.get('OD_CYL','')}  {p.get('OD_EJE','')}")
    y -= 20
    c.drawString(72, y, f"OI: {p.get('OI_SPH','')}  {p.get('OI_CYL','')}  {p.get('OI_EJE','')}")
    y -= 30
    for lbl in ("DP_Lejos", "DP_CERCA", "ADD"):
        if p.get(lbl):
            c.drawString(72, y, f"{lbl}: {p[lbl]}"); y -= 18
    c.line(400, 100, 520, 100); c.drawString(435, 85, "Firma")
    c.save(); buf.write(open(tmp, "rb").read()); os.remove(tmp); buf.seek(0); return buf

# -----------------------------------------------------------------------
#                        Interfaz: encabezado
# -----------------------------------------------------------------------

def header():
    st.image("logo.png", use_container_width=True)
    st.markdown("<h2 style='text-align:center'>👓 Sistema de Gestión BMA Ópticas</h2>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align:center;color:gray'>Cuidamos tus ojos, cuidamos de ti</h4>", unsafe_allow_html=True)

# -----------------------------------------------------------------------
#                        Pantalla: Inicio
# -----------------------------------------------------------------------

def pantalla_inicio(df: pd.DataFrame):
    st.header("🏠 Inicio")
    col1, col2, col3 = st.columns(3)
    col1.metric("Pacientes", len(df))
    col2.metric("Con receta", df["OD_SPH"].notna().sum() if "OD_SPH" in df else 0)
    col3.metric("Ventas", f"${df['Valor'].sum():,.0f}" if "Valor" in df else "$0")

# -----------------------------------------------------------------------
#                        Pantalla: Registrar venta
# -----------------------------------------------------------------------

def registrar_venta(df: pd.DataFrame):
    st.header("💰 Registrar Venta")

    with st.form("form_venta", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            rut_input = st.text_input("RUT* (sólo números, K opcional)")
            nombre_in = st.text_input("Nombre*")
            edad_in   = st.number_input("Edad*", 0, 120, format="%i")
            tel_in    = st.text_input("Teléfono")
        with c2:
            tipo_lente = st.selectbox("Tipo de lente", ["Monofocal", "Bifocal", "Progresivo"])
            armazon_in = st.text_input("Armazón")
            crist_in   = st.text_input("Cristales")
            valor_in   = st.number_input("Valor venta*", 0, step=5000, format="%i")
            pago_in    = st.selectbox("Forma de pago", ["Efectivo", "T. Crédito", "Débito"])
            fecha_in   = st.date_input("Fecha venta", dt.date.today())

        st.markdown("##### Datos ópticos (opcional)")
        co1, co2, co3 = st.columns(3)
        with co1:
            od_sph = st.text_input("OD ESF"); od_cyl = st.text_input("OD CIL"); od_eje = st.text_input("OD EJE")
        with co2:
            oi_sph = st.text_input("
