import os
import shutil
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
import magic

# ══════════════════ CONFIGURACIÓN ══════════════════
st.set_page_config(
    page_title="BMA Ópticas",
    page_icon="👓",
    layout="wide"
)
logging.basicConfig(
    filename="app.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

DATAFILE = "Pacientes.xlsx"
BACKUP_DIR = "backups"
VALID_MIME = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel"
}
BASE_COLUMNS = [
    "RUT", "Nombre", "Edad", "Teléfono",
    "Tipo_Lente", "Armazon", "Cristales",
    "Valor", "Forma_Pago", "Fecha_venta",
    "OD_SPH","OD_CYL","OD_EJE",
    "OI_SPH","OI_CYL","OI_EJE",
    "DP_Lejos","DP_CERCA","ADD"
]

# ══════════════════ UTILIDADES ══════════════════
def validar_rut(r: str) -> bool:
    """Valida cuerpo+DV del RUT chileno (sin puntos ni guión)."""
    s = r.upper().replace(".", "").replace("-", "")
    if not re.fullmatch(r"[0-9]{7,8}[0-9K]", s):
        return False
    cuerpo, dv = s[:-1], s[-1]
    suma, factor = 0, 2
    for c in reversed(cuerpo):
        suma += int(c) * factor
        factor = 2 if factor == 7 else factor + 1
    dv_calc = 11 - (suma % 11)
    dv_calc = {10: "K", 11: "0"}.get(dv_calc, str(dv_calc))
    return dv == dv_calc

def formatear_rut(r: str) -> str:
    """Le da formato 12.345.678-5 a un RUT sin puntos."""
    s = r.replace(".", "").replace("-", "").upper()
    cuerpo, dv = s[:-1], s[-1]
    cuerpo = f"{int(cuerpo):,}".replace(",", ".")
    return f"{cuerpo}-{dv}"

def es_excel_valido(path: str) -> bool:
    try:
        mime = magic.from_file(path, mime=True)
        return mime in VALID_MIME
    except Exception as e:
        logging.error(f"MIME error: {e}")
        return False

# ══════════════════ CARGA / GUARDADO ══════════════════
def cargar_datos() -> pd.DataFrame:
    """Carga o crea el Excel garantizando columnas base."""
    if not os.path.exists(DATAFILE) or not es_excel_valido(DATAFILE):
        return pd.DataFrame(columns=BASE_COLUMNS)
    df = pd.read_excel(DATAFILE).copy()
    for col in BASE_COLUMNS:
        if col not in df.columns:
            df[col] = "" if col != "Valor" else 0
    # Aseguramos que Fecha_venta sea datetime
    if df["Fecha_venta"].dtype == object:
        df["Fecha_venta"] = pd.to_datetime(df["Fecha_venta"], errors="coerce")
    return df[BASE_COLUMNS]

def guardar_df(df: pd.DataFrame):
    """Hace backup y sobreescribe el Excel."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = os.path.join(BACKUP_DIR, f"Pacientes_{ts}.xlsx")
    try:
        shutil.copy(DATAFILE, backup)
    except FileNotFoundError:
        pass
    try:
        df.to_excel(DATAFILE, index=False)
    except Exception as e:
        st.warning(f"⚠️ Error guardando datos: {e}")

# ══════════════════ PDF RECETA ══════════════════
def generar_pdf_receta(p: Dict[str, Any]) -> BytesIO:
    tmp = f"tmp_{uuid.uuid4()}.pdf"
    buf = BytesIO()
    c = canvas.Canvas(tmp, pagesize=letter)
    c.setTitle(f"Receta {p['Nombre']}")
    # Encabezado
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, 750, "BMA Ópticas – Receta Óptica")
    c.setFont("Helvetica", 12)
    c.drawString(72, 730, f"Paciente: {escape(p['Nombre'])}")
    c.drawString(72, 712, f"RUT: {p['RUT']}")
    c.drawString(400, 712, dt.datetime.now().strftime("%d/%m/%Y"))
    # Tabla ESF/CIL/EJE
    y = 680
    c.setFont("Helvetica-Bold", 12)
    c.drawString(72, y, "OD / OI   ESF   CIL   EJE")
    y -= 20
    c.setFont("Helvetica", 12)
    c.drawString(72, y, f"OD: {p['OD_SPH']}  {p['OD_CYL']}  {p['OD_EJE']}")
    y -= 20
    c.drawString(72, y, f"OI: {p['OI_SPH']}  {p['OI_CYL']}  {p['OI_EJE']}")
    # Extras
    y -= 30
    for label in ["DP_Lejos","DP_CERCA","ADD"]:
        if p[label]:
            c.drawString(72, y, f"{label.replace('_',' ')}: {p[label]}")
            y -= 18
    # Firma
    c.line(400, 100, 520, 100)
    c.drawString(430, 85, "Firma Óptico")
    c.save()
    with open(tmp, "rb") as f:
        buf.write(f.read())
    os.remove(tmp)
    buf.seek(0)
    return buf

# ══════════════════ UI COMPONENTES ══════════════════
def header():
    if os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)
    st.markdown(
        "<h2 style='text-align:center'>👓 Sistema de Gestión BMA Ópticas</h2>"
        "<h4 style='text-align:center;color:gray'>Cuidamos tus ojos, cuidamos de ti</h4>",
        unsafe_allow_html=True
    )

def registrar_venta(df: pd.DataFrame) -> pd.DataFrame:
    st.subheader("💰 Registrar Venta")
    with st.form("venta", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            rut_in = st.text_input("RUT* (números y K)", max_chars=12)
            nombre = st.text_input("Nombre*").strip()
            edad = st.number_input("Edad*", min_value=0, max_value=120, value=0)
            telefono = st.text_input("Teléfono")
        with c2:
            tipo_lente = st.selectbox("Tipo de lente", ["Monofocal","Bifocal","Progresivo"])
            armazon = st.text_input("Armazón")
            cristales = st.text_input("Cristales")
            valor = st.number_input("Valor venta*", min_value=0, step=1000)
            forma = st.selectbox("Forma de pago", ["Efectivo","T. Crédito","T. Débito"])
        fecha = st.date_input("Fecha de venta", dt.date.today())
        st.markdown("**Datos ópticos (opcional)**")
        od_sph = st.text_input("OD ESF"); od_cyl = st.text_input("OD CIL"); od_eje = st.text_input("OD EJE")
        oi_sph = st.text_input("OI ESF"); oi_cyl = st.text_input("OI CIL"); oi_eje = st.text_input("OI EJE")
        dp_lejos = st.text_input("DP Lejos"); dp_cerca = st.text_input("DP Cerca"); add = st.text_input("ADD")
        enviar = st.form_submit_button("Guardar")

    if not enviar:
        return df

    # Validaciones
    raw = rut_in.replace(".", "").replace("-", "").upper()
    if not validar_rut(raw):
        st.error("❌ RUT inválido")
        return df
    rut_fmt = formatear_rut(raw)

    if not nombre:
        st.error("❌ Nombre obligatorio")
        return df
    nombre = " ".join(w.capitalize() for w in nombre.split())

    # Preparamos registro
    nueva = {
        "RUT":       rut_fmt,
        "Nombre":    nombre,
        "Edad":      int(edad),
        "Teléfono":  telefono,
        "Tipo_Lente":tipo_lente,
        "Armazon":   armazon,
        "Cristales": cristales,
        "Valor":     int(valor),
        "Forma_Pago":forma,
        "Fecha_venta":pd.to_datetime(fecha),
        "OD_SPH":    od_sph, "OD_CYL": od_cyl, "OD_EJE": od_eje,
        "OI_SPH":    oi_sph, "OI_CYL": oi_cyl, "OI_EJE": oi_eje,
        "DP_Lejos":  dp_lejos, "DP_CERCA": dp_cerca, "ADD": add
    }

    df = pd.concat([df, pd.DataFrame([nueva])], ignore_index=True)
    guardar_df(df)
    st.success("✅ Venta registrada")
    st.session_state.df = df
    return df

def pantalla_pacientes(df: pd.DataFrame):
    st.subheader("👁️ Pacientes / Historial")
    if df.empty:
        st.info("No hay registros aún")
        return
    for rut, grp in df.groupby("RUT"):
        pac = grp.iloc[-1]
        with st.expander(f"{pac['Nombre']}  –  {rut}  ({len(grp)} ventas)"):
            tabla = grp[["Fecha_venta","Tipo_Lente","Valor","Forma_Pago","Armazon","Cristales"]]
            tabla = tabla.sort_values("Fecha_venta", ascending=False).rename(columns={"Fecha_venta":"Fecha"})
            st.dataframe(tabla, use_container_width=True)
            if any([pac[col] for col in ("OD_SPH","OI_SPH")]):
                if st.button("📄 Descargar Receta", key=f"pdf_{rut}"):
                    pdf = generar_pdf_receta(pac.to_dict())
                    st.download_button(
                        "⬇️ Descargar", pdf,
                        file_name=f"Receta_{pac['Nombre'].replace(' ','_')}.pdf",
                        mime="application/pdf",
                        key=f"dl_{rut}"
                    )

def pantalla_reportes(df: pd.DataFrame):
    st.subheader("📊 Reportes")
    if df.empty:
        st.info("No hay datos para reportar")
        return

    min_d = df["Fecha_venta"].min().date()
    max_d = df["Fecha_venta"].max().date()
    desde, hasta = st.date_input("Rango de fechas", [min_d, max_d], min_value=min_d, max_value=max_d)
    mask = (df["Fecha_venta"].dt.date >= desde) & (df["Fecha_venta"].dt.date <= hasta)
    data = df[mask]

    st.markdown("### 🔑 Estadísticas clave")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total ventas", f"${data['Valor'].sum():,.0f}")
    c2.metric("Ticket medio", f"${data['Valor'].mean():,.0f}")
    c3.metric("Venta máx.", f"${data['Valor'].max():,.0f}")
    c4.metric("Venta mín.", f"${data['Valor'].min():,.0f}")

    st.markdown("### 📈 Ventas por mes")
    vm = (data.assign(Mes=data["Fecha_venta"].dt.to_period("M"))
             .groupby("Mes")["Valor"].sum()
             .reset_index())
    vm["Mes"] = vm["Mes"].astype(str)
    st.line_chart(vm.set_index("Mes")["Valor"])

    st.markdown("### 💳 Ventas por tipo de lente")
    vt = data.groupby("Tipo_Lente")["Valor"].sum()
    st.bar_chart(vt)

def pantalla_inicio(df: pd.DataFrame):
    st.subheader("🏠 Inicio")
    if df.empty:
        st.info("Aún no hay ventas")
        return
    u = df["RUT"].nunique()
    t = df["Valor"].sum()
    m = df["Valor"].mean()
    c1, c2, c3 = st.columns(3)
    c1.metric("Pacientes únicos", u)
    c2.metric("Total ventas", f"${t:,.0f}")
    c3.metric("Ticket medio", f"${m:,.0f}")
    st.write(df.tail(5))

# ══════════════════ MAIN ══════════════════
if "df" not in st.session_state:
    st.session_state.df = cargar_datos()

header()
menu = st.sidebar.radio("Menú", [
    "🏠 Inicio",
    "💰 Registrar venta",
    "👁️ Pacientes",
    "📊 Reportes"
])

if menu == "🏠 Inicio":
    pantalla_inicio(st.session_state.df)
elif menu == "💰 Registrar venta":
    st.session_state.df = registrar_venta(st.session_state.df)
elif menu == "👁️ Pacientes":
    pantalla_pacientes(st.session_state.df)
else:
    pantalla_reportes(st.session_state.df)

st.sidebar.markdown("---")
st.sidebar.caption("BMA Ópticas © 2025")
