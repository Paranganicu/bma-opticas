# app.py
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
import magic  # Funciona en Streamlit Cloud

# ───────────── CONFIGURACIÓN BÁSICA ─────────────
st.set_page_config(page_title="BMA Ópticas", page_icon="👓", layout="wide")
logging.basicConfig(
    filename="app.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

DATAFILE = "Pacientes.xlsx"
COLUMNAS = [
    "RUT","Nombre","Edad","Teléfono",
    "Tipo_Lente","Armazon","Cristales",
    "Valor","Forma_Pago","Fecha_Venta",
    "OD_SPH","OD_CYL","OD_EJE",
    "OI_SPH","OI_CYL","OI_EJE",
    "DP_Lejos","DP_CERCA","ADD"
]
MIME_XLSX = [
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel"
]

# ───────────── UTILIDADES ─────────────
def validar_rut(raw: str) -> bool:
    """Valida RUT chileno sin puntos ni guión."""
    r = raw.upper().replace(".", "").replace("-", "")
    if not re.fullmatch(r"[0-9]{7,8}[0-9K]", r):
        return False
    cuerpo, dv = r[:-1], r[-1]
    suma, m = 0, 2
    for c in reversed(cuerpo):
        suma += int(c) * m
        m = 2 if m == 7 else m + 1
    dv_calc = 11 - (suma % 11)
    dv_calc = {10: "K", 11: "0"}.get(dv_calc, str(dv_calc))
    return dv == dv_calc

def formatear_rut(raw: str) -> str:
    """Transforma '12345678K' en '12.345.678-K'."""
    r = raw.upper().replace(".", "").replace("-", "")
    cuerpo, dv = r[:-1], r[-1]
    cuerpo_num = f"{int(cuerpo):,}".replace(",", ".")
    return f"{cuerpo_num}-{dv}"

def es_excel_valido(path: str) -> bool:
    try:
        mime = magic.from_file(path, mime=True)
        return mime in MIME_XLSX
    except:
        return False

def cargar_datos() -> pd.DataFrame:
    """Carga o crea el Excel con todas las columnas."""
    if not os.path.exists(DATAFILE) or not es_excel_valido(DATAFILE):
        return pd.DataFrame(columns=COLUMNAS)
    df = pd.read_excel(DATAFILE)
    # Asegura que existan todas las columnas
    for c in COLUMNAS:
        if c not in df.columns:
            df[c] = "" if df.get(c, None) is None else 0
    return df[COLUMNAS]

def guardar_datos(df: pd.DataFrame):
    try:
        df.to_excel(DATAFILE, index=False)
    except Exception as e:
        st.warning(f"⚠️ No se pudo guardar: {e}")

def generar_pdf(pac: Dict[str, Any]) -> BytesIO:
    """Genera PDF de receta óptica."""
    buf = BytesIO()
    tmp = f"tmp_{uuid.uuid4()}.pdf"
    c = canvas.Canvas(tmp, pagesize=letter)
    c.setTitle(f"Receta {pac['Nombre']}")
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, 750, "BMA Ópticas – Receta Óptica")
    c.setFont("Helvetica", 12)
    c.drawString(72, 730, f"Paciente: {escape(pac['Nombre'])}")
    c.drawString(72, 712, f"RUT: {pac['RUT']}")
    c.drawString(400, 712, dt.datetime.now().strftime("%d/%m/%Y"))
    y = 680
    c.setFont("Helvetica-Bold", 12)
    c.drawString(72, y, "OD / OI   ESF   CIL   EJE"); y -= 20
    c.setFont("Helvetica", 12)
    c.drawString(72, y, f"OD: {pac['OD_SPH']}  {pac['OD_CYL']}  {pac['OD_EJE']}"); y -= 20
    c.drawString(72, y, f"OI: {pac['OI_SPH']}  {pac['OI_CYL']}  {pac['OI_EJE']}"); y -= 30
    for label in ("DP_Lejos","DP_CERCA","ADD"):
        if pac[label]:
            c.drawString(72, y, f"{label.replace('_',' ')}: {pac[label]}")
            y -= 18
    c.line(400, 100, 520, 100)
    c.drawString(430, 85, "Firma Óptico")
    c.save()
    with open(tmp, "rb") as f:
        buf.write(f.read())
    os.remove(tmp)
    buf.seek(0)
    return buf

# ───────────── CALLBACKS ─────────────
def _cb_format_rut():
    raw = st.session_state["rut"]
    clean = raw.upper().replace(".", "").replace("-", "")
    if validar_rut(clean):
        st.session_state["rut"] = formatear_rut(clean)

def _cb_capitalize_name():
    name = st.session_state["nombre"].strip()
    st.session_state["nombre"] = " ".join(w.capitalize() for w in name.split())

# ───────────── INTERFAZ ─────────────
def header():
    if os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)
    st.markdown(
        "<h2 style='text-align:center;'>👓 Sistema de Gestión BMA Ópticas</h2>"
        "<h4 style='text-align:center;color:gray;'>Cuidamos tus ojos, cuidamos de ti</h4>",
        unsafe_allow_html=True
    )

def pantalla_inicio(df: pd.DataFrame):
    st.header("🏠 Inicio")
    if df.empty:
        st.info("Sin datos aún")
        return
    c1, c2, c3 = st.columns(3)
    c1.metric("Pacientes únicos", df["RUT"].nunique())
    c2.metric("Ventas totales", f"${df['Valor'].sum():,.0f}")
    c3.metric("Ticket medio", f"${df['Valor'].mean():,.0f}")
    st.dataframe(df.tail())

def registrar_venta(df: pd.DataFrame) -> pd.DataFrame:
    st.header("💰 Registrar venta")

    with st.form("venta", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            st.text_input(
                "RUT*",
                key="rut",
                placeholder="sólo números y K",
                on_change=_cb_format_rut
            )
            st.text_input(
                "Nombre*",
                key="nombre",
                on_change=_cb_capitalize_name
            )
            edad = st.number_input("Edad*", min_value=0, max_value=120, step=1, key="edad")
            telefono = st.text_input("Teléfono", key="telefono")
        with col2:
            tipo = st.selectbox("Tipo lente", ["Monofocal","Bifocal","Progresivo"], key="tipo")
            armazon = st.text_input("Armazón", key="armazon")
            cristales = st.text_input("Cristales", key="cristales")
            valor = st.number_input("Valor venta*", min_value=0, step=1000, key="valor")
            forma = st.selectbox("Forma pago", ["Efectivo","T. Crédito","T. Débito"], key="forma")
        fecha = st.date_input("Fecha venta", dt.date.today(), key="fecha")

        st.markdown("### Datos ópticos (opcionales)")
        od_sph = st.text_input("OD ESF", key="OD_SPH")
        od_cyl = st.text_input("OD CIL", key="OD_CYL")
        od_eje = st.text_input("OD EJE", key="OD_EJE")
        oi_sph = st.text_input("OI ESF", key="OI_SPH")
        oi_cyl = st.text_input("OI CIL", key="OI_CYL")
        oi_eje = st.text_input("OI EJE", key="OI_EJE")
        dp_lejos = st.text_input("DP Lejos", key="DP_Lejos")
        dp_cerca = st.text_input("DP Cerca", key="DP_CERCA")
        add = st.text_input("ADD", key="ADD")

        ok = st.form_submit_button("Guardar venta")

    if not ok:
        return df

    # Validaciones esenciales
    if not validar_rut(st.session_state["rut"]):
        st.error("❌ RUT inválido")
        return df
    if not st.session_state["nombre"].strip():
        st.error("❌ Nombre obligatorio")
        return df
    if st.session_state["valor"] <= 0:
        st.error("❌ Valor debe ser > 0")
        return df

    registro = {
        "RUT": st.session_state["rut"],
        "Nombre": st.session_state["nombre"],
        "Edad": int(st.session_state["edad"]),
        "Teléfono": st.session_state["telefono"],
        "Tipo_Lente": st.session_state["tipo"],
        "Armazon": st.session_state["armazon"],
        "Cristales": st.session_state["cristales"],
        "Valor": int(st.session_state["valor"]),
        "Forma_Pago": st.session_state["forma"],
        "Fecha_Venta": pd.to_datetime(st.session_state["fecha"]),
        "OD_SPH": od_sph, "OD_CYL": od_cyl, "OD_EJE": od_eje,
        "OI_SPH": oi_sph, "OI_CYL": oi_cyl, "OI_EJE": oi_eje,
        "DP_Lejos": dp_lejos, "DP_CERCA": dp_cerca, "ADD": add
    }

    df = pd.concat([df, pd.DataFrame([registro])], ignore_index=True)
    guardar_datos(df)
    st.success("✅ Venta registrada")
    return df

def pantalla_pacientes(df: pd.DataFrame):
    st.header("👁️ Pacientes")
    if df.empty:
        st.info("Sin registros")
        return
    for rut, grupo in df.groupby("RUT"):
        pac = grupo.iloc[-1]
        with st.expander(f"{pac['Nombre']} — {rut} ({len(grupo)} ventas)"):
            st.table(
                grupo[["Fecha_Venta","Tipo_Lente","Valor","Forma_Pago","Armazon","Cristales"]]
                .rename(columns={"Fecha_Venta":"Fecha"})
                .sort_values("Fecha", ascending=False)
            )
            if pac["OD_SPH"] or pac["OI_SPH"]:
                if st.button("📄 PDF rec.", key=f"pdf_{rut}"):
                    pdf = generar_pdf(pac.to_dict())
                    st.download_button(
                        "Descargar PDF",
                        data=pdf,
                        file_name=f"Receta_{pac['Nombre'].replace(' ','_')}.pdf",
                        mime="application/pdf",
                        key=f"dl_{rut}"
                    )

# ───────────── EJECUCIÓN PRINCIPAL ─────────────
if "df" not in st.session_state:
    st.session_state.df = cargar_datos()

header()
st.sidebar.markdown("## Menú")
seleccion = st.sidebar.radio(
    "",
    ("🏠 Inicio","💰 Registrar venta","👁️ Pacientes")
)

if seleccion == "🏠 Inicio":
    pantalla_inicio(st.session_state.df)
elif seleccion == "💰 Registrar venta":
    st.session_state.df = registrar_venta(st.session_state.df)
else:
    pantalla_pacientes(st.session_state.df)

st.sidebar.markdown("---")
st.sidebar.caption("© BMA Ópticas 2025")
