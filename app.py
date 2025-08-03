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
import magic  # validar MIME en Streamlit Cloud

# ───────────────── CONFIG GLOBAL ─────────────────
st.set_page_config(page_title="BMA Ópticas", page_icon="👓", layout="wide")
logging.basicConfig(filename="app.log", level=logging.INFO,
                    format="%(asctime)s — %(levelname)s — %(message)s")

ARCHIVO_XLSX = "Pacientes.xlsx"
COLUM_OPT = [
    "OD_SPH", "OD_CYL", "OD_EJE", "OI_SPH", "OI_CYL", "OI_EJE",
    "DP_Lejos", "DP_CERCA", "ADD"
]
MIME_XLSX = {
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

# ───────────────── UTILIDADES ─────────────────
RUT_RE = re.compile(r"^([0-9]{1,3}(?:\.[0-9]{3})*)-([0-9K])$")

def validar_rut(rut: str) -> bool:
    """Valida RUT chileno con formato 12.345.678-5"""
    rut = rut.upper().strip()
    m = RUT_RE.match(rut)
    if not m:
        return False
    cuerpo = m.group(1).replace(".", "")
    dv_ing = m.group(2)
    suma, fac = 0, 2
    for d in reversed(cuerpo):
        suma += int(d) * fac
        fac = 2 if fac == 7 else fac + 1
    dv_calc = 11 - (suma % 11)
    dv_calc = {10: "K", 11: "0"}.get(dv_calc, str(dv_calc))
    return dv_ing == dv_calc

def normalizar_rut(rut: str) -> str:
    rut = rut.upper().replace(".", "").replace("-", "")
    return f"{int(rut[:-1]):,}".replace(",", ".") + "-" + rut[-1]

def enmascarar_rut(rut: str) -> str:
    if "-" not in rut:
        return rut
    cuerpo, dv = rut.split("-")
    cuerpo = cuerpo[:-4] + "****" if len(cuerpo) > 4 else cuerpo
    return f"{cuerpo}-{dv}"

def excel_valido(path: str) -> bool:
    try:
        return magic.from_file(path, mime=True) in MIME_XLSX
    except Exception as e:
        logging.error(f"MIME error: {e}")
        return False

# ───────────────── DATA ─────────────────
@st.cache_data(ttl=3600, hash_funcs={pd.DataFrame: lambda _: None})
def cargar_datos() -> pd.DataFrame:
    if not os.path.exists(ARCHIVO_XLSX):
        return pd.DataFrame()
    if not excel_valido(ARCHIVO_XLSX):
        st.error("Archivo XLSX inválido")
        return pd.DataFrame()
    df = pd.read_excel(ARCHIVO_XLSX)
    df.columns = df.columns.str.strip()
    if "Rut" in df:
        df["Rut"] = df["Rut"].astype(str).apply(normalizar_rut)
    if "Nombre" in df:
        df["Nombre"] = df["Nombre"].str.title().str.strip()
    if "Valor" in df:
        df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce").fillna(0)
    if "Última_visita" in df:
        df["Última_visita"] = pd.to_datetime(df["Última_visita"], errors="coerce")
    for col in COLUM_OPT:
        if col in df:
            df[col] = df[col].fillna("")
    return df

def guardar_datos(df: pd.DataFrame):
    try:
        df.to_excel(ARCHIVO_XLSX, index=False)
    except Exception as e:
        st.warning(f"No se pudo guardar: {e}")

# ───────────────── PDF ─────────────────

def pdf_receta(p: Dict[str, Any]) -> BytesIO:
    tmp = f"tmp_{uuid.uuid4()}.pdf"
    buf = BytesIO()
    try:
        c = canvas.Canvas(tmp, pagesize=letter)
        c.setTitle(f"Receta – {p.get('Nombre','')}")
        c.setFont("Helvetica-Bold", 14)
        c.drawString(72, 750, "BMA Ópticas – Receta")
        c.setFont("Helvetica", 11)
        c.drawString(72, 730, f"Paciente: {escape(p.get('Nombre',''))}")
        c.drawString(72, 712, f"RUT: {enmascarar_rut(p.get('Rut',''))}")
        c.drawString(400, 712, dt.datetime.now().strftime("%d/%m/%Y"))
        y = 680
        for etiqueta, od_key, oi_key in [
            ("ESF", "OD_SPH", "OI_SPH"),
            ("CIL", "OD_CYL", "OI_CYL"),
            ("EJE", "OD_EJE", "OI_EJE")
        ]:
            c.drawString(72, y, f"{etiqueta}: {p.get(od_key,'')}  /  {p.get(oi_key,'')}")
            y -= 18
        for extra in ["DP_Lejos", "DP_CERCA", "ADD"]:
            if p.get(extra):
                c.drawString(72, y, f"{extra}: {p[extra]}")
                y -= 16
        c.line(400, 100, 520, 100)
        c.drawString(430, 85, "Firma Óptico")
        c.save(); buf.write(open(tmp, "rb").read())
    finally:
        if os.path.exists(tmp): os.remove(tmp)
    buf.seek(0); return buf

# ───────────────── UI ─────────────────

def encabezado():
    st.image("logo.png", use_container_width=True)
    st.markdown("<h2 style='text-align:center;'>👓 Sistema de Gestión BMA Ópticas</h2>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align:center;color:gray;'>Cuidamos tus ojos, cuidamos de ti</h4>", unsafe_allow_html=True)

# ───────────────── FORMULARIO VENTA ─────────────────

def formulario_venta(df: pd.DataFrame):
    st.header("🛒 Registrar venta y receta")
    with st.form("venta", clear_on_submit=True):
        st.subheader("Paciente")
        col1, col2, col3 = st.columns(3)
        with col1:
            rut_raw = st.text_input("RUT* (con puntos y guion)")
        with col2:
            nombre = st.text_input("Nombre completo*")
        with col3:
            edad = st.number_input("Edad*", 0, 120, step=1, format="%d")
        telefono = st.text_input("Teléfono")
        st.subheader("Venta")
        c1, c2, c3 = st.columns(3)
        with c1:
            tipo_lente = st.selectbox("Tipo de lente", ["Monofocal", "Bifocal", "Progresivo"])
        with c2:
            armazon = st.text_input("Armazón")
        with c3:
            valor = st.number_input("Valor $", 0, step=1000, format="%d")
        forma_pago = st.selectbox("Forma de pago", ["Efectivo", "Tarjeta", "Transferencia"])
        fecha = st.date_input("Fecha venta", dt.date.today())
        st.subheader("Receta (opcional)")
        r1, r2, r3 = st.columns(3)
        with r1:
            od_sph = st.text_input("OD ESF")
            oi_sph = st.text
