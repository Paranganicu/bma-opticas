import os
import re
import uuid
import logging
import datetime as dt
from io import BytesIO
from typing import Dict, Any

import pandas as pd
import streamlit as st
from html import escape
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
import magic  # linux / Streamlit-Cloud OK

# ───────── CONFIGURACIÓN BÁSICA ─────────
st.set_page_config(
    page_title="BMA Ópticas",
    page_icon="👓",
    layout="wide"
)
logging.basicConfig(
    filename="app.log",
    level=logging.INFO,
    format="%(asctime)s – %(levelname)s – %(message)s"
)

DATAFILE = "Pacientes.xlsx"
COLUMNAS_BASE = [
    "RUT","Nombre","Edad","Teléfono",
    "Tipo_Lente","Armazon","Cristales",
    "Valor","Forma_Pago","Fecha_venta",
    "OD_SPH","OD_CYL","OD_EJE",
    "OI_SPH","OI_CYL","OI_EJE",
    "DP_Lejos","DP_CERCA","ADD"
]
MIME_XLSX = [
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel"
]

# ───────── UTILIDADES ─────────
def validar_rut(r: str) -> bool:
    """Valida RUT (sin puntos ni guión) con dígito verificador."""
    r = r.upper().replace(".", "").replace("-", "")
    if not re.fullmatch(r"[0-9]{7,8}[0-9K]", r):
        return False
    cuerpo, dv = r[:-1], r[-1]
    s, m = 0, 2
    for c in reversed(cuerpo):
        s += int(c) * m
        m = 2 if m == 7 else m + 1
    dv_calc = 11 - (s % 11)
    dv_calc = {11: "0", 10: "K"}.get(dv_calc, str(dv_calc))
    return dv == dv_calc

def formatear_rut(r: str) -> str:
    """Recibe RUT limpio (solo dígitos y K) y devuelve 12.345.678-5."""
    r = r.replace(".", "").replace("-", "").upper()
    cuerpo, dv = r[:-1], r[-1]
    # formatea miles con punto
    cuerpo = f"{int(cuerpo):,}".replace(",", ".")
    return f"{cuerpo}-{dv}"

def es_excel_valido(path: str) -> bool:
    """Comprueba MIME real del archivo Excel."""
    try:
        return magic.from_file(path, mime=True) in MIME_XLSX
    except Exception as e:
        logging.error(f"MIME check error: {e}")
        return False

# ───────── CARGA / GUARDADO DE DATOS ─────────
@st.cache_data(ttl=3600, hash_funcs={pd.DataFrame: lambda _: None})
def cargar_datos() -> pd.DataFrame:
    """Lee (o crea) el Excel y garantiza todas las columnas."""
    if not os.path.exists(DATAFILE) or not es_excel_valido(DATAFILE):
        # retorna DataFrame vacío con columnas base
        return pd.DataFrame(columns=COLUMNAS_BASE)
    df = pd.read_excel(DATAFILE).copy()
    # añade columnas faltantes con valor por defecto
    for col in COLUMNAS_BASE:
        if col not in df.columns:
            df[col] = 0 if col == "Valor" else ""
    # convertimos la fecha de venta
    df["Fecha_venta"] = pd.to_datetime(df["Fecha_venta"], errors="coerce")
    return df[COLUMNAS_BASE]

def guardar_df(df: pd.DataFrame):
    """Guarda el DataFrame en disco."""
    try:
        df.to_excel(DATAFILE, index=False)
    except Exception as e:
        st.warning(f"⚠️ No se pudo guardar en disco: {e}")

# ───────── GENERACIÓN DE PDF ─────────
def generar_pdf_receta(pac: Dict[str, Any]) -> BytesIO:
    """Genera un PDF con la receta óptica."""
    tmp = f"tmp_{uuid.uuid4()}.pdf"
    buf = BytesIO()
    c = canvas.Canvas(tmp, pagesize=letter)
    c.setTitle(f"Receta Óptica – {pac['Nombre']}")
    # encabezado
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, 750, "BMA Ópticas – Receta Óptica")
    # datos paciente
    c.setFont("Helvetica", 12)
    c.drawString(72, 730, f"Paciente: {escape(pac['Nombre'])}")
    c.drawString(72, 712, f"RUT: {pac['RUT']}")
    c.drawString(400, 712, dt.datetime.now().strftime("%d/%m/%Y"))
    # tabla ESF/CIL/EJE
    y = 680
    c.setFont("Helvetica-Bold", 12)
    c.drawString(72, y, "OD / OI    ESF   CIL   EJE"); y -= 20
    c.setFont("Helvetica", 12)
    c.drawString(72, y, f"OD: {pac['OD_SPH']}  {pac['OD_CYL']}  {pac['OD_EJE']}"); y -= 20
    c.drawString(72, y, f"OI: {pac['OI_SPH']}  {pac['OI_CYL']}  {pac['OI_EJE']}"); y -= 30
    # extras DP y ADD
    for lab in ("DP_Lejos","DP_CERCA","ADD"):
        if pac[lab]:
            c.drawString(72, y, f"{lab.replace('_',' ')}: {pac[lab]}")
            y -= 18
    # firma
    c.line(400, 100, 520, 100)
    c.drawString(430, 85, "Firma Óptico")
    c.save()
    with open(tmp, "rb") as f:
        buf.write(f.read())
    os.remove(tmp)
    buf.seek(0)
    return buf

# ───────── INTERFAZ ─────────
def header():
    if os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)
    st.markdown(
        "<h2 style='text-align:center;'>👓 Sistema de Gestión BMA Ópticas</h2>"
        "<h4 style='text-align:center;color:gray;'>Cuidamos tus ojos, cuidamos de ti</h4>",
        unsafe_allow_html=True
    )

# ───────── VENTAS (ÚNICO FORMULARIO) ─────────
def registrar_venta(df: pd.DataFrame) -> pd.DataFrame:
    st.subheader("💰 Registrar venta")
    with st.form("venta", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            rut_raw = st.text_input("RUT* (solo números y K)")
            nombre  = st.text_input("Nombre*")
            edad    = st.number_input("Edad*", min_value=0, max_value=120, step=1)
            telefono= st.text_input("Teléfono")
        with c2:
            tipo_lente = st.selectbox("Tipo de lente", ["Monofocal","Bifocal","Progresivo"])
            armazon    = st.text_input("Armazón")
            cristales  = st.text_input("Cristales")
            valor      = st.number_input("Valor venta*", min_value=0, step=1000)
            forma_pago = st.selectbox("Forma de pago", ["Efectivo","T. Crédito","T. Débito"])
        fecha_venta = st.date_input("Fecha de venta", dt.date.today())

        st.markdown("### Datos ópticos (opcionales)")
        o1, o2, o3 = st.columns(3)
        OD_SPH = o1.text_input("OD ESF")
        OD_CYL = o2.text_input("OD CIL")
        OD_EJE = o3.text_input("OD EJE")
        OI_SPH = o1.text_input("OI ESF")
        OI_CYL = o2.text_input("OI CIL")
        OI_EJE = o3.text_input("OI EJE")
        DP_Lejos  = o1.text_input("DP Lejos")
        DP_CERCA  = o2.text_input("DP Cerca")
        ADD       = o3.text_input("ADD")

        enviar = st.form_submit_button("Guardar venta")

    if not enviar:
        return df

    # validaciones básicas
    rut_clean = rut_raw.replace(".","").replace("-","").upper()
    if not validar_rut(rut_clean):
        st.error("❌ RUT inválido"); return df
    rut_fmt = formatear_rut(rut_clean)

    if not nombre.strip():
        st.error("❌ Nombre obligatorio"); return df
    nombre = " ".join(w.capitalize() for w in nombre.split())

    # construye registro de venta
    venta = {
        "RUT": rut_fmt,
        "Nombre": nombre,
        "Edad": int(edad),
        "Teléfono": telefono,
        "Tipo_Lente": tipo_lente,
        "Armazon": armazon,
        "Cristales": cristales,
        "Valor": int(valor),
        "Forma_Pago": forma_pago,
        "Fecha_venta": pd.to_datetime(fecha_venta),
        "OD_SPH": OD_SPH, "OD_CYL": OD_CYL, "OD_EJE": OD_EJE,
        "OI_SPH": OI_SPH, "OI_CYL": OI_CYL, "OI_EJE": OI_EJE,
        "DP_Lejos": DP_Lejos, "DP_CERCA": DP_CERCA, "ADD": ADD
    }

    df = pd.concat([df, pd.DataFrame([venta])], ignore_index=True)
    guardar_df(df)
    st.success("✅ Venta registrada")
    st.session_state.df = df
    return df

# ───────── HISTORIAL DE PACIENTES ─────────
def pantalla_pacientes(df: pd.DataFrame):
    st.subheader("👁️ Pacientes")
    if df.empty:
        st.info("Sin registros aún"); return
    for rut, grp in df.groupby("RUT"):
        pac = grp.iloc[-1]
        with st.expander(f"{pac['Nombre']} – {rut} ({len(grp)} ventas)"):
            st.write(
                grp[["Fecha_venta","Tipo_Lente","Valor","Forma_Pago","Armazon","Cristales"]]
                .sort_values("Fecha_venta", ascending=False)
                .rename(columns={"Fecha_venta":"Fecha"})
            )
            if (pac["OD_SPH"] or pac["OI_SPH"]) and st.button("📄 PDF", key=f"pdf_{rut}"):
                pdf = generar_pdf_receta(pac.to_dict())
                st.download_button(
                    "Descargar receta",
                    pdf,
                    file_name=f"Receta_{pac['Nombre'].replace(' ','_')}.pdf",
                    mime="application/pdf",
                    key=f"dl_{rut}"
                )

# ───────── RESUMEN INICIAL ─────────
def pantalla_inicio(df: pd.DataFrame):
    st.subheader("🏠 Inicio")
    if df.empty:
        st.info("Sin datos aún"); return
    c1, c2, c3 = st.columns(3)
    c1.metric("Pacientes únicos", df["RUT"].nunique())
    c2.metric("Ventas totales", f"${df['Valor'].sum():,.0f}")
    c3.metric("Ticket medio", f"${df['Valor'].mean():,.0f}")
    st.write(df.tail(5))

# ───────── MAIN ─────────
if "df" not in st.session_state:
    st.session_state.df = cargar_datos()

header()
menu = st.sidebar.radio(
    "Menú",
    ["🏠 Inicio", "💰 Registrar venta", "👁️ Pacientes"]
)

if menu == "🏠 Inicio":
    pantalla_inicio(st.session_state.df)
elif menu == "💰 Registrar venta":
    st.session_state.df = registrar_venta(st.session_state.df)
else:
    pantalla_pacientes(st.session_state.df)

st.sidebar.markdown("---")
st.sidebar.caption("BMA Ópticas © 2025")
