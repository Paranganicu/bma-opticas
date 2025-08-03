import os
import shutil
import logging
import datetime as dt
from io import BytesIO
from typing import Dict, Any

import pandas as pd
import streamlit as st
from html import escape
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float
from sqlalchemy.orm import sessionmaker, declarative_base

# ══════════════════ CONFIGURACIÓN ══════════════════
st.set_page_config(page_title="BMA Ópticas", page_icon="👓", layout="wide")
logging.basicConfig(filename="app.log", level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")

DB_FILE = "optica.db"
BACKUP_DIR = "backups"
DATABASE_URL = f"sqlite:///{DB_FILE}"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# ══════════════════ MODELO ORM ══════════════════
class Venta(Base):
    __tablename__ = "ventas"
    id = Column(Integer, primary_key=True, index=True)
    RUT = Column(String)
    Nombre = Column(String)
    Edad = Column(Integer)
    Teléfono = Column(String)
    Tipo_Lente = Column(String)
    Armazon = Column(String)
    Cristales = Column(String)
    Valor = Column(Float)
    Forma_Pago = Column(String)
    Fecha_venta = Column(DateTime)
    OD_SPH = Column(String)
    OD_CYL = Column(String)
    OD_EJE = Column(String)
    OI_SPH = Column(String)
    OI_CYL = Column(String)
    OI_EJE = Column(String)
    DP_Lejos = Column(String)
    DP_CERCA = Column(String)
    ADD = Column(String)

# Crear DB si no existe
Base.metadata.create_all(bind=engine)

# ══════════════════ UTILIDADES ══════════════════
def backup_db():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"optica_{ts}.db")
    try:
        shutil.copy(DB_FILE, backup_path)
    except Exception as e:
        logging.warning(f"Backup falló: {e}")

def validar_rut(r: str) -> bool:
    import re
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
    s = r.replace(".", "").replace("-", "").upper()
    cuerpo, dv = s[:-1], s[-1]
    cuerpo = f"{int(cuerpo):,}".replace(",", ".")
    return f"{cuerpo}-{dv}"

def generar_pdf_receta(p: Dict[str, Any]) -> BytesIO:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setTitle(f"Receta {p['Nombre']}")
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, 750, "BMA Ópticas – Receta Óptica")
    c.setFont("Helvetica", 12)
    c.drawString(72, 730, f"Paciente: {escape(p['Nombre'])}")
    c.drawString(72, 712, f"RUT: {p['RUT']}")
    c.drawString(400, 712, dt.datetime.now().strftime("%d/%m/%Y"))
    y = 680
    c.setFont("Helvetica-Bold", 12)
    c.drawString(72, y, "OD / OI   ESF   CIL   EJE")
    y -= 20
    c.setFont("Helvetica", 12)
    c.drawString(72, y, f"OD: {p['OD_SPH']}  {p['OD_CYL']}  {p['OD_EJE']}")
    y -= 20
    c.drawString(72, y, f"OI: {p['OI_SPH']}  {p['OI_CYL']}  {p['OI_EJE']}")
    y -= 30
    for label in ["DP_Lejos","DP_CERCA","ADD"]:
        if p[label]:
            c.drawString(72, y, f"{label.replace('_',' ')}: {p[label]}")
            y -= 18
    c.line(400, 100, 520, 100)
    c.drawString(430, 85, "Firma Óptico")
    c.save()
    buf.seek(0)
    return buf

# ══════════════════ FUNCIONES DB ══════════════════
def insertar_venta(data: Dict[str, Any]):
    session = SessionLocal()
    try:
        venta = Venta(**data)
        session.add(venta)
        session.commit()
    except Exception as e:
        st.error(f"❌ Error insertando venta: {e}")
        session.rollback()
    finally:
        session.close()

def leer_ventas() -> pd.DataFrame:
    session = SessionLocal()
    try:
        ventas = session.query(Venta).all()
        df = pd.DataFrame([v.__dict__ for v in ventas])
        if not df.empty:
            df = df.drop("_sa_instance_state", axis=1)
        return df
    finally:
        session.close()

# ══════════════════ UI ══════════════════
def header():
    if os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)
    st.markdown("<h2 style='text-align:center'>👓 Sistema de Gestión BMA Ópticas</h2>"
                "<h4 style='text-align:center;color:gray'>Cuidamos tus ojos, cuidamos de ti</h4>", unsafe_allow_html=True)

def registrar_venta():
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
        return

    raw = rut_in.replace(".", "").replace("-", "").upper()
    if not validar_rut(raw):
        st.error("❌ RUT inválido")
        return
    rut_fmt = formatear_rut(raw)

    if not nombre:
        st.error("❌ Nombre obligatorio")
        return

    data = {
        "RUT": rut_fmt,
        "Nombre": nombre.title(),
        "Edad": int(edad),
        "Teléfono": telefono,
        "Tipo_Lente": tipo_lente,
        "Armazon": armazon,
        "Cristales": cristales,
        "Valor": float(valor),
        "Forma_Pago": forma,
        "Fecha_venta": pd.to_datetime(fecha),
        "OD_SPH": od_sph, "OD_CYL": od_cyl, "OD_EJE": od_eje,
        "OI_SPH": oi_sph, "OI_CYL": oi_cyl, "OI_EJE": oi_eje,
        "DP_Lejos": dp_lejos, "DP_CERCA": dp_cerca, "ADD": add
    }

    insertar_venta(data)
    backup_db()
    st.success("✅ Venta registrada")

def pantalla_pacientes():
    st.subheader("👁️ Pacientes / Historial")
    df = leer_ventas()
    if df.empty:
        st.info("No hay registros aún")
        return
    for rut, grp in df.groupby("RUT"):
        pac = grp.iloc[-1]
        with st.expander(f"{pac['Nombre']} – {rut} ({len(grp)} ventas)"):
            tabla = grp[["Fecha_venta","Tipo_Lente","Valor","Forma_Pago","Armazon","Cristales"]]
            tabla = tabla.sort_values("Fecha_venta", ascending=False).rename(columns={"Fecha_venta":"Fecha"})
            st.dataframe(tabla, use_container_width=True)
            if any([pac[col] for col in ("OD_SPH","OI_SPH")]):
                if st.button("📄 Descargar Receta", key=f"pdf_{rut}"):
                    pdf = generar_pdf_receta(pac.to_dict())
                    st.download_button("⬇️ Descargar", pdf,
                        file_name=f"Receta_{pac['Nombre'].replace(' ','_')}.pdf",
                        mime="application/pdf", key=f"dl_{rut}")

def pantalla_reportes():
    st.subheader("📊 Reportes")
    df = leer_ventas()
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

def pantalla_inicio():
    st.subheader("🏠 Inicio")
    df = leer_ventas()
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
# Siempre tener un DataFrame disponible para cálculos globales
df = leer_ventas()

header()
menu = st.sidebar.radio("Menú", ["🏠 Inicio", "💰 Registrar venta", "👁️ Pacientes", "📊 Reportes"])

if menu == "🏠 Inicio":
    pantalla_inicio()
elif menu == "💰 Registrar venta":
    registrar_venta()
elif menu == "👁️ Pacientes":
    pantalla_pacientes()
else:
    pantalla_reportes()

st.sidebar.markdown("---")
st.sidebar.caption("BMA Ópticas © 2025")
