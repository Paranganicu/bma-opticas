
# app.py
import os, re, uuid, logging, datetime as dt
from io import BytesIO
from typing import Dict, Any

import pandas as pd
import streamlit as st
from html import escape
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import magic

# ─────────────── CONFIG ───────────────
st.set_page_config(
    page_title="BMA Ópticas v3.2",
    page_icon="👓",
    layout="wide"
)
logging.basicConfig(
    filename="app.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

DATAFILE = "Pacientes.xlsx"
BASE_COLUMNS = [
    "RUT","Nombre","Edad","Teléfono",
    "Tipo_Lente","Armazon","Cristales","Valor","Forma_Pago","Fecha_Venta",
    "OD_SPH","OD_CYL","OD_EJE","OI_SPH","OI_CYL","OI_EJE","DP_Lejos","DP_Cerca","ADD"
]
XLSX_MIMES = [
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel"
]

# ─────────────── UTIL ───────────────
def validar_rut(raw: str) -> bool:
    r = raw.upper().replace(".", "").replace("-", "")
    if not re.fullmatch(r"[0-9]{7,8}[0-9K]", r):
        return False
    cuerpo, dv = r[:-1], r[-1]
    s, m = 0, 2
    for c in reversed(cuerpo):
        s += int(c) * m
        m = 2 if m == 7 else m+1
    dv_calc = 11 - (s % 11)
    dv_calc = {10:"K",11:"0"}.get(dv_calc, str(dv_calc))
    return dv == dv_calc

def formatear_rut(raw: str) -> str:
    r = raw.upper().replace(".", "").replace("-", "")
    cuerpo, dv = r[:-1], r[-1]
    # formatear con miles: 12345678 -> 12.345.678
    cuerpo_fmt = f"{int(cuerpo):,}".replace(",", ".")
    return f"{cuerpo_fmt}-{dv}"

def es_excel_valido(path: str) -> bool:
    try:
        return magic.from_file(path, mime=True) in XLSX_MIMES
    except Exception:
        return False

def cargar_datos() -> pd.DataFrame:
    if not os.path.exists(DATAFILE) or not es_excel_valido(DATAFILE):
        # DataFrame vacío con columnas base
        return pd.DataFrame(columns=BASE_COLUMNS)
    df = pd.read_excel(DATAFILE).copy()
    # asegurar todas las columnas
    for c in BASE_COLUMNS:
        if c not in df.columns:
            df[c] = "" if c not in ("Valor",) else 0
    return df[BASE_COLUMNS]

def guardar_datos(df: pd.DataFrame):
    try:
        df.to_excel(DATAFILE, index=False)
    except Exception as e:
        st.warning(f"⚠️ No se pudo guardar: {e}")

def generar_pdf(pac: Dict[str,Any]) -> BytesIO:
    tmp = f"/tmp/{uuid.uuid4()}.pdf"
    buf = BytesIO()
    c = canvas.Canvas(tmp, pagesize=letter)
    c.setTitle(f"Receta_{pac['Nombre']}")
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72,750,"BMA Ópticas – Receta Óptica")
    c.setFont("Helvetica", 12)
    c.drawString(72,730,f"Paciente: {escape(pac['Nombre'])}")
    c.drawString(72,712,f"RUT: {pac['RUT']}")
    c.drawString(400,712,dt.datetime.now().strftime("%d/%m/%Y"))
    y=680
    c.setFont("Helvetica-Bold",12); c.drawString(72,y,"OD / OI    ESF   CIL   EJE"); y-=20
    c.setFont("Helvetica",12)
    c.drawString(72,y,f"OD: {pac['OD_SPH']}  {pac['OD_CYL']}  {pac['OD_EJE']}"); y-=20
    c.drawString(72,y,f"OI: {pac['OI_SPH']}  {pac['OI_CYL']}  {pac['OI_EJE']}"); y-=30
    for fld,label in [("DP_Lejos","DP Lejos"),("DP_Cerca","DP Cerca"),("ADD","ADD")]:
        if pac.get(fld):
            c.drawString(72,y,f"{label}: {pac[fld]}"); y-=18
    c.line(400,100,520,100); c.drawString(430,85,"Firma Óptico")
    c.save()
    with open(tmp,"rb") as f: buf.write(f.read())
    os.remove(tmp)
    buf.seek(0)
    return buf

# ─────────────── UI ───────────────
def mostrar_header():
    if os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)
    st.markdown(
        "<h2 style='text-align:center;'>👓 Sistema de Gestión BMA Ópticas</h2>"
        "<h4 style='text-align:center;color:gray;'>Cuidamos tus ojos, cuidamos de ti.</h4>",
        unsafe_allow_html=True
    )

def pantalla_registrar_venta(df: pd.DataFrame) -> pd.DataFrame:
    st.subheader("💰 Registrar venta")
    with st.form("form_venta", clear_on_submit=True):
        c1,c2 = st.columns(2)
        with c1:
            rut_raw = st.text_input("RUT* (sólo números y K)")
            nombre  = st.text_input("Nombre*", placeholder="Nombre Apellido")
            edad    = st.number_input("Edad*", min_value=0, max_value=120, step=1, value=30)
            telefono= st.text_input("Teléfono")
        with c2:
            tipo_l  = st.selectbox("Tipo de lente", ["Monofocal","Bifocal","Progresivo"])
            armaz   = st.text_input("Armazón")
            crist   = st.text_input("Cristales")
            valor   = st.number_input("Valor venta*", min_value=0, step=1000)
            fpago   = st.selectbox("Forma de pago", ["Efectivo","T. Crédito","T. Débito"])
        fecha_v = st.date_input("Fecha venta", dt.date.today())
        st.markdown("#### Datos ópticos (opcional)")
        od_sph  = st.text_input("OD ESF"); od_cyl  = st.text_input("OD CIL"); od_eje = st.text_input("OD EJE")
        oi_sph  = st.text_input("OI ESF"); oi_cyl  = st.text_input("OI CIL"); oi_eje = st.text_input("OI EJE")
        dp_l    = st.text_input("DP Lejos"); dp_c    = st.text_input("DP Cerca"); add = st.text_input("ADD")
        ok = st.form_submit_button("Guardar venta")

    if not ok:
        return df

    # validaciones
    raw = rut_raw.strip().upper().replace(".","").replace("-","")
    if not validar_rut(raw):
        st.error("❌ RUT inválido")
        return df
    rut_fmt = formatear_rut(raw)
    if not nombre.strip():
        st.error("❌ Nombre obligatorio")
        return df
    nombre = " ".join(w.capitalize() for w in nombre.split())

    row = {
        "RUT":rut_fmt,"Nombre":nombre,"Edad":int(edad),"Teléfono":telefono,
        "Tipo_Lente":tipo_l,"Armazon":armaz,"Cristales":crist,
        "Valor":int(valor),"Forma_Pago":fpago,"Fecha_Venta":pd.to_datetime(fecha_v),
        "OD_SPH":od_sph,"OD_CYL":od_cyl,"OD_EJE":od_eje,
        "OI_SPH":oi_sph,"OI_CYL":oi_cyl,"OI_EJE":oi_eje,
        "DP_Lejos":dp_l,"DP_Cerca":dp_c,"ADD":add
    }
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    guardar_datos(df)
    st.success("✅ Venta registrada")
    return df

def pantalla_pacientes(df: pd.DataFrame):
    st.subheader("👁️ Pacientes")
    if df.empty:
        st.info("No hay registros aún")
        return
    for rut,grp in df.groupby("RUT"):
        pac = grp.iloc[-1]
        with st.expander(f"{pac['Nombre']} – {rut} ({len(grp)} ventas)"):
            st.dataframe(
                grp[["Fecha_Venta","Tipo_Lente","Valor","Forma_Pago","Armazon","Cristales"]]
                .sort_values("Fecha_Venta", ascending=False)
                .rename(columns={"Fecha_Venta":"Fecha"})
            )
            if (pac["OD_SPH"] or pac["OI_SPH"]) and st.button("📄 PDF", key=f"pdf_{rut}"):
                pdf = generar_pdf(pac.to_dict())
                st.download_button(
                    "Descargar receta",
                    data=pdf,
                    file_name=f"Receta_{pac['Nombre'].replace(' ','_')}.pdf",
                    mime="application/pdf",
                    key=f"dl_{rut}"
                )

def pantalla_reportes(df: pd.DataFrame):
    st.subheader("📊 Reportes")
    if df.empty:
        st.info("No hay datos")
        return

    ventas = df[df["Valor"]>0]
    col1,col2,col3 = st.columns(3)
    col1.metric("Ventas totales", f"${ventas['Valor'].sum():,.0f}")
    col2.metric("Ticket promedio", f"${ventas['Valor'].mean():,.0f}")
    col3.metric("Pacientes únicos", df["RUT"].nunique())

    st.markdown("---")
    st.write("**Ventas por tipo de lente**")
    st.bar_chart(ventas.groupby("Tipo_Lente")["Valor"].sum())

    st.markdown("---")
    ventas["Mes"] = ventas["Fecha_Venta"].dt.to_period("M").astype(str)
    st.write("**Evolución mensual**")
    st.line_chart(ventas.groupby("Mes")["Valor"].sum())

def pantalla_inicio(df: pd.DataFrame):
    st.subheader("🏠 Inicio")
    if df.empty:
        st.info("Sin datos aún")
        return
    ultimo = df.tail(5)
    st.dataframe(ultimo)

# ─────────────── MAIN ───────────────
if "df" not in st.session_state:
    st.session_state.df = cargar_datos()

mostrar_header()
menu = st.sidebar.radio("Menú", ["🏠 Inicio","💰 Registrar venta","👁️ Pacientes","📊 Reportes"])
df = st.session_state.df

if menu == "🏠 Inicio":
    pantalla_inicio(df)
elif menu == "💰 Registrar venta":
    st.session_state.df = pantalla_registrar_venta(df)
elif menu == "👁️ Pacientes":
    pantalla_pacientes(df)
else:
    pantalla_reportes(df)

st.sidebar.markdown("---")
st.sidebar.caption("© BMA Ópticas 2025")
