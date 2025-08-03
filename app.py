# ─────────── app.py ───────────
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
import magic  # linux / Streamlit Cloud OK

# ─────────── Configuración global ───────────
st.set_page_config(page_title="BMA Ópticas", page_icon="👓", layout="wide")
logging.basicConfig(
    filename="app.log", level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

DATAFILE = "Pacientes.xlsx"
COLUMNS = [
    "RUT", "Nombre", "Edad", "Teléfono",
    "Tipo_Lente", "Armazon", "Cristales",
    "Valor", "Forma_Pago", "Fecha_venta",
    # ópticos
    "OD_SPH","OD_CYL","OD_EJE",
    "OI_SPH","OI_CYL","OI_EJE",
    "DP_Lejos","DP_CERCA","ADD"
]
VALID_MIME = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel"
}

# ─────────── Utilidades ───────────
def validar_rut(rut: str) -> bool:
    r = rut.upper().replace(".", "").replace("-", "")
    if not re.fullmatch(r"[0-9]{7,8}[0-9K]", r): return False
    cuerpo, dv = r[:-1], r[-1]
    suma, mul = 0, 2
    for c in reversed(cuerpo):
        suma += int(c) * mul
        mul = mul + 1 if mul < 7 else 2
    dv_calc = 11 - (suma % 11)
    dv_calc = {10: "K", 11: "0"}.get(dv_calc, str(dv_calc))
    return dv == dv_calc

def formatear_rut(rut: str) -> str:
    r = rut.replace(".", "").replace("-", "").upper()
    cuerpo, dv = r[:-1], r[-1]
    # separa miles con puntos
    cuerpo = f"{int(cuerpo):,}".replace(",", ".")
    return f"{cuerpo}-{dv}"

def es_excel_valido(path: str) -> bool:
    try:
        mime = magic.from_file(path, mime=True)
        return mime in VALID_MIME
    except:
        return False

def cargar_datos() -> pd.DataFrame:
    """Carga o crea DataFrame con todas las columnas."""
    if not os.path.exists(DATAFILE) or not es_excel_valido(DATAFILE):
        return pd.DataFrame(columns=COLUMNS)
    df = pd.read_excel(DATAFILE).copy()
    # asegurar columnas
    for c in COLUMNS:
        if c not in df.columns:
            df[c] = "" if c not in ("Valor",) else 0
    return df[COLUMNS]

def guardar_df(df: pd.DataFrame):
    try:
        df.to_excel(DATAFILE, index=False)
    except Exception as e:
        st.warning(f"⚠️ No se pudo guardar: {e}")

# ─────────── Generación de PDF ───────────
def generar_pdf(pac: Dict[str,Any]) -> BytesIO:
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
    # tabla básica
    y = 680
    c.setFont("Helvetica-Bold", 12)
    c.drawString(72, y, "OD / OI    ESF   CIL   EJE"); y -= 20
    c.setFont("Helvetica", 12)
    c.drawString(72, y, f"OD: {pac['OD_SPH']}  {pac['OD_CYL']}  {pac['OD_EJE']}"); y -= 20
    c.drawString(72, y, f"OI: {pac['OI_SPH']}  {pac['OI_CYL']}  {pac['OI_EJE']}"); y -= 30
    for opt in ("DP_Lejos","DP_CERCA","ADD"):
        if pac.get(opt):
            c.drawString(72, y, f"{opt.replace('_',' ')}: {pac[opt]}"); y-=18
    # firma
    c.line(400, 100, 520, 100)
    c.drawString(430, 85, "Firma Óptico")
    c.save()
    with open(tmp, "rb") as f: buf.write(f.read())
    os.remove(tmp)
    buf.seek(0)
    return buf

# ─────────── UI: HEADER ───────────
def mostrar_header():
    if os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)
    st.markdown(
        "<h2 style='text-align:center;'>👓 Sistema de Gestión BMA Ópticas</h2>"
        "<h4 style='text-align:center;color:gray;'>Cuidamos tus ojos, cuidamos de ti</h4>",
        unsafe_allow_html=True
    )

# ─────────── UI: Registrar venta ───────────
def registrar_venta(df: pd.DataFrame) -> pd.DataFrame:
    st.header("💰 Registrar venta")
    with st.form("venta", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            rut_raw = st.text_input("RUT* (sólo dígitos y K)")
            nombre_raw = st.text_input("Nombre*")
            edad = st.number_input("Edad*", min_value=0, max_value=120, step=1, value=0)
            telefono = st.text_input("Teléfono")
        with c2:
            tipo_lente = st.selectbox("Tipo de lente", ["Monofocal","Bifocal","Progresivo"])
            armazon = st.text_input("Armazón")
            cristales = st.text_input("Cristales")
            valor = st.number_input("Valor venta*", min_value=0, step=1000, value=0)
            forma_pago = st.selectbox("Forma de pago", ["Efectivo","T. Crédito","T. Débito"])
        fecha_venta = st.date_input("Fecha de venta", dt.date.today())
        st.markdown("#### Datos ópticos (opcional)")
        od_esf = st.text_input("OD ESF", key="od_esf")
        od_cyl = st.text_input("OD CIL", key="od_cyl")
        od_eje = st.text_input("OD EJE", key="od_eje")
        oi_esf = st.text_input("OI ESF", key="oi_esf")
        oi_cyl = st.text_input("OI CIL", key="oi_cyl")
        oi_eje = st.text_input("OI EJE", key="oi_eje")
        dp_lejos = st.text_input("DP Lejos", key="dp_lejos")
        dp_cerca = st.text_input("DP Cerca", key="dp_cerca")
        add = st.text_input("ADD", key="add")
        ok = st.form_submit_button("Guardar venta")

    if not ok:
        return df

    # — Validaciones —
    ruts = rut_raw.strip().replace(".", "").replace("-", "").upper()
    if not validar_rut(ruts):
        st.error("❌ RUT inválido")
        return df
    rut = formatear_rut(ruts)
    if not nombre_raw.strip():
        st.error("❌ Nombre obligatorio")
        return df
    nombre = " ".join(w.capitalize() for w in nombre_raw.split())

    venta = {
        "RUT": rut,
        "Nombre": nombre,
        "Edad": int(edad),
        "Teléfono": telefono,
        "Tipo_Lente": tipo_lente,
        "Armazon": armazon,
        "Cristales": cristales,
        "Valor": int(valor),
        "Forma_Pago": forma_pago,
        "Fecha_venta": pd.to_datetime(fecha_venta),
        "OD_SPH": od_esf, "OD_CYL": od_cyl, "OD_EJE": od_eje,
        "OI_SPH": oi_esf, "OI_CYL": oi_cyl, "OI_EJE": oi_eje,
        "DP_Lejos": dp_lejos, "DP_CERCA": dp_cerca, "ADD": add
    }
    df = pd.concat([df, pd.DataFrame([venta])], ignore_index=True)
    guardar_df(df)
    st.success("✅ Venta registrada")
    return df

# ─────────── UI: Pacientes / Historial ───────────
def pantalla_pacientes(df: pd.DataFrame):
    st.header("👁️ Pacientes")
    if df.empty:
        st.info("Sin datos aún"); return
    for rut, grp in df.groupby("RUT"):
        pac = grp.iloc[-1]
        with st.expander(f"{pac['Nombre']}  –  {rut}  ({len(grp)} ventas)"):
            st.table(
                grp[["Fecha_venta","Tipo_Lente","Valor","Forma_Pago","Armazon","Cristales"]]
                .sort_values("Fecha_venta", ascending=False)
                .rename(columns={"Fecha_venta":"Fecha"})
            )
            if pac["OD_SPH"] or pac["OI_SPH"]:
                if st.button("📄 Descargar receta", key=f"pdf_{rut}"):
                    pdf = generar_pdf(pac.to_dict())
                    st.download_button(
                        "⬇️ PDF",
                        pdf,
                        file_name=f"Receta_{pac['Nombre'].replace(' ','_')}.pdf",
                        mime="application/pdf",
                        key=f"dl_{rut}"
                    )

# ─────────── UI: Inicio / Resumen ───────────
def pantalla_inicio(df: pd.DataFrame):
    st.header("🏠 Inicio")
    if df.empty:
        st.info("Aún no hay ventas"); return
    col1, col2, col3 = st.columns(3)
    col1.metric("Pacientes únicos", df["RUT"].nunique())
    col2.metric("Ventas totales", f"${df['Valor'].sum():,.0f}")
    col3.metric("Ticket medio", f"${df['Valor'].mean():,.0f}")
    st.dataframe(df.tail())

# ─────────── MAIN ───────────
df = st.session_state.get("df", cargar_datos())
mostrar_header()
op = st.sidebar.radio("Menú", ["🏠 Inicio","💰 Registrar venta","👁️ Pacientes"])
if op == "🏠 Inicio":
    pantalla_inicio(df)
elif op == "💰 Registrar venta":
    df = registrar_venta(df)
    st.session_state.df = df
else:
    pantalla_pacientes(df)

st.sidebar.markdown("---")
st.sidebar.caption("BMA Ópticas © 2025")
