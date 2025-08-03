# ───────────────  app.py  ───────────────
import os, re, uuid, datetime as dt, logging
from io import BytesIO
from typing import Dict, Any

import pandas as pd
import streamlit as st
from html import escape
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
import magic   # funciona en Streamlit Cloud

# ═════════════ CONFIG GLOBAL ═════════════
st.set_page_config("BMA Ópticas", "👓", layout="wide")
logging.basicConfig(filename="app.log",
                    level=logging.INFO,
                    format="%(asctime)s  %(levelname)s  %(message)s")

DATAFILE = "Pacientes.xlsx"
COLUMNAS_BASE = [
    "RUT", "Nombre", "Edad", "Teléfono",
    "Tipo_Lente", "Armazon", "Cristales",
    "Valor", "Forma_Pago", "Fecha_venta",
    # ópticos
    "OD_SPH","OD_CYL","OD_EJE",
    "OI_SPH","OI_CYL","OI_EJE",
    "DP_Lejos","DP_CERCA","ADD"
]
# mime-types válidos para Excel
MIME_XLSX = ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
             "application/vnd.ms-excel"]

# ═════════════ UTILIDADES ═════════════
def validar_rut(r: str) -> bool:
    """true si el RUT completo (sin puntos) es válido"""
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
    """123456785  ->  12.345.678-5"""
    r = r.replace(".", "").replace("-", "").upper()
    cuerpo, dv = r[:-1], r[-1]
    cuerpo = f"{int(cuerpo):,}".replace(",", ".")
    return f"{cuerpo}-{dv}"

def es_excel_valido(f: str) -> bool:
    try:
        return magic.from_file(f, mime=True) in MIME_XLSX
    except Exception as e:
        logging.error(f"mime-check: {e}")
        return False

def cargar_datos() -> pd.DataFrame:
    """Lee (o crea) el Excel y garantiza columnas."""
    if not os.path.exists(DATAFILE) or not es_excel_valido(DATAFILE):
        # crea DataFrame vacío con columnas base
        return pd.DataFrame(columns=COLUMNAS_BASE)
    df = pd.read_excel(DATAFILE).copy()
    # añade cualquier columna faltante
    for col in COLUMNAS_BASE:
        if col not in df.columns:
            df[col] = "" if col != "Valor" else 0
    return df[COLUMNAS_BASE]

def guardar_df(df: pd.DataFrame):
    try:
        df.to_excel(DATAFILE, index=False)
    except Exception as e:
        st.warning(f"⚠️ No se pudo guardar en disco: {e}")

# ═════════════ PDF RECETA ═════════════
def pdf_receta(pac: Dict[str,Any]) -> BytesIO:
    tmp, buf = f"tmp_{uuid.uuid4()}.pdf", BytesIO()
    c = canvas.Canvas(tmp, pagesize=letter)
    c.setTitle(f"Receta {pac['Nombre']}")
    c.setFont("Helvetica-Bold", 16); c.drawString(72, 750, "BMA Ópticas – Receta")
    c.setFont("Helvetica", 12)
    c.drawString(72, 730, f"Paciente: {escape(pac['Nombre'])}")
    c.drawString(72, 712, f"RUT: {pac['RUT']}")
    c.drawString(400, 712, dt.datetime.now().strftime("%d/%m/%Y"))
    y = 680
    c.setFont("Helvetica-Bold", 12); c.drawString(72, y, "OD / OI    ESF   CIL   EJE"); y -= 20
    c.setFont("Helvetica", 12)
    c.drawString(72, y, f"OD: {pac['OD_SPH']}  {pac['OD_CYL']}  {pac['OD_EJE']}"); y -= 20
    c.drawString(72, y, f"OI: {pac['OI_SPH']}  {pac['OI_CYL']}  {pac['OI_EJE']}"); y -= 30
    for lab in ("DP_Lejos", "DP_CERCA", "ADD"):
        if pac[lab]:
            c.drawString(72, y, f"{lab.replace('_', ' ')}: {pac[lab]}"); y -= 18
    c.line(400, 100, 520, 100); c.drawString(430, 85, "Firma Óptico")
    c.save(); buf.write(open(tmp, "rb").read()); os.remove(tmp); buf.seek(0)
    return buf

# ═════════════ UI HEADER ═════════════
def header():
    if os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)
    st.markdown("<h2 style='text-align:center;'>👓 Sistema de Gestión BMA Ópticas</h2>"
                "<h4 style='text-align:center;color:gray;'>Cuidamos tus ojos, cuidamos de ti</h4>",
                unsafe_allow_html=True)

# ═════════════ VENTAS (punto único de entrada) ═════════════
def registrar_venta(df: pd.DataFrame) -> pd.DataFrame:
    st.subheader("💰 Registrar venta")

    with st.form("venta"):
        cols1, cols2 = st.columns(2)

        with cols1:
            rut  = st.text_input("RUT* (sólo números y K)")
            nombre = st.text_input("Nombre*", placeholder="Nombre Apellido")
            edad = st.number_input("Edad*", min_value=0, max_value=120, step=1, value=0)
            telefono = st.text_input("Teléfono")
        with cols2:
            tipo_lente = st.selectbox("Tipo de lente", ["Monofocal","Bifocal","Progresivo"])
            armazon    = st.text_input("Armazón")
            cristales  = st.text_input("Cristales")
            valor      = st.number_input("Valor venta*", min_value=0, step=1000)
            forma_pago = st.selectbox("Forma de pago", ["Efectivo","T. Crédito","T. Débito"])
        fecha_venta = st.date_input("Fecha de venta", dt.date.today())

        st.markdown("### Datos ópticos (opcional)")
        c1,c2,c3 = st.columns(3)
        OD_SPH = c1.text_input("OD ESF"); OD_CYL = c2.text_input("OD CIL"); OD_EJE = c3.text_input("OD EJE")
        OI_SPH = c1.text_input("OI ESF"); OI_CYL = c2.text_input("OI CIL"); OI_EJE = c3.text_input("OI EJE")
        DP_Lejos  = c1.text_input("DP Lejos"); DP_CERCA = c2.text_input("DP Cerca"); ADD = c3.text_input("ADD")

        ok = st.form_submit_button("Guardar")

    if not ok: return df   # aún no envía

    # ---------- Validaciones ----------
    rut_raw = rut.strip().replace(".", "").replace("-", "").upper()
    if not validar_rut(rut_raw):
        st.error("❌ RUT inválido"); return df

    rut_fmt = formatear_rut(rut_raw)

    if not nombre.strip():
        st.error("❌ El nombre es obligatorio"); return df
    nombre = " ".join(w.capitalize() for w in nombre.split())

    # ---------- Inserción / actualización ----------
    venta = {
        "RUT": rut_fmt, "Nombre": nombre, "Edad": int(edad), "Teléfono": telefono,
        "Tipo_Lente": tipo_lente, "Armazon": armazon, "Cristales": cristales,
        "Valor": int(valor), "Forma_Pago": forma_pago,
        "Fecha_venta": pd.to_datetime(fecha_venta),
        "OD_SPH": OD_SPH, "OD_CYL": OD_CYL, "OD_EJE": OD_EJE,
        "OI_SPH": OI_SPH, "OI_CYL": OI_CYL, "OI_EJE": OI_EJE,
        "DP_Lejos": DP_Lejos, "DP_CERCA": DP_CERCA, "ADD": ADD
    }

    df = pd.concat([df, pd.DataFrame([venta])], ignore_index=True)
    guardar_df(df)
    st.success("✅ Venta registrada")
    st.session_state.df = df   # persistencia en sesión
    return df

# ═════════════ PACIENTES / HISTORIALES ═════════════
def pantalla_pacientes(df: pd.DataFrame):
    st.subheader("👁️ Pacientes")
    if df.empty:
        st.info("No hay registros"); return

    for rut, grp in df.groupby("RUT"):
        pac = grp.iloc[-1]  # último registro
        with st.expander(f"{pac['Nombre']}  –  {rut}  ({len(grp)} ventas)"):
            st.write(grp[["Fecha_venta","Tipo_Lente","Valor","Forma_Pago","Armazon","Cristales"]]
                     .sort_values("Fecha_venta", ascending=False)
                     .rename(columns={"Fecha_venta":"Fecha"}))
            receta_ok = pac["OD_SPH"] or pac["OI_SPH"]
            if receta_ok and st.button("📄 PDF", key=f"pdf_{rut}"):
                pdf = pdf_receta(pac.to_dict())
                st.download_button("Descargar receta", pdf,
                                   file_name=f"Receta_{pac['Nombre'].replace(' ','_')}.pdf",
                                   mime="application/pdf", key=f"dl_{rut}")

# ═════════════ INICIO / RESUMEN ═════════════
def inicio(df: pd.DataFrame):
    st.subheader("🏠 Inicio")
    if df.empty:
        st.info("Sin datos aún"); return
    c1,c2,c3 = st.columns(3)
    c1.metric("Pacientes únicos", df["RUT"].nunique())
    c2.metric("Ventas totales", f"${df['Valor'].sum():,.0f}")
    c3.metric("Ticket medio", f"${df['Valor'].mean():,.0f}")
    st.write(df.tail())

# ═════════════ MAIN ═════════════
if "df" not in st.session_state:
    st.session_state.df = cargar_datos()

header()
menu = st.sidebar.radio("Menú", ["🏠 Inicio","💰 Registrar venta","👁️ Pacientes"])

if menu == "🏠 Inicio":
    inicio(st.session_state.df)
elif menu == "💰 Registrar venta":
    st.session_state.df = registrar_venta(st.session_state.df)
else:
    pantalla_pacientes(st.session_state.df)

st.sidebar.markdown("---")
st.sidebar.caption("BMA Ópticas © 2025")
# ───────────────  fin app.py  ───────────────
