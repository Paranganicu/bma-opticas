# ─────────────────── 1. IMPORTS Y CONFIG GLOBAL ───────────────────
import os, re, uuid, logging, datetime as dt
from io import BytesIO
from typing import Dict, Any

import pandas as pd
import streamlit as st
from html import escape
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import magic                # ok en Streamlit Cloud

st.set_page_config(page_title="BMA Ópticas", page_icon="👓", layout="wide")
logging.basicConfig(filename="app.log",
                    level=logging.INFO,
                    format="%(asctime)s — %(levelname)s — %(message)s")

DATA_PATH     = "Pacientes.xlsx"
COLUMNAS_OPT  = ["OD_SPH","OD_CYL","OD_EJE","OI_SPH","OI_CYL","OI_EJE",
                 "DP_Lejos","DP_CERCA","ADD"]
MIME_VALIDOS  = ["application/vnd.ms-excel",
                 "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]

# ─────────────────── 2. UTILIDADES ───────────────────
def validar_rut(rut: str) -> bool:
    rut = rut.upper().replace(".","").replace("-","")
    if not re.match(r"^[0-9]{7,8}[0-9K]$", rut): return False
    cuerpo, dv = rut[:-1], rut[-1]
    suma, fac = 0, 2
    for c in reversed(cuerpo):
        suma += int(c)*fac
        fac   = 2 if fac == 7 else fac+1
    dv_ok = 11 - (suma % 11)
    dv_ok = {10:"K", 11:"0"}.get(dv_ok, str(dv_ok))
    return dv == dv_ok

def mascarar_rut(rut:str)->str:
    if "-" not in rut: return rut
    cuerpo, dv = rut.split("-")
    return f"{cuerpo[:-4]}****-{dv}" if len(cuerpo)>4 else rut

def excel_ok(path:str)->bool:
    try:  return magic.from_file(path, mime=True) in MIME_VALIDOS
    except: return False

def capitalizar(txt:str)->str:
    return " ".join(w.capitalize() for w in txt.strip().split())

# ─────────────────── 3. CARGA & GUARDADO DE DATOS ───────────────────
@st.cache_data(ttl=600, hash_funcs={pd.DataFrame:lambda _: None})
def cargar_datos()->pd.DataFrame:
    if not os.path.exists(DATA_PATH):               # primera vez
        return pd.DataFrame()                       # DataFrame vacío
    if not excel_ok(DATA_PATH):
        st.error("❌ 'Pacientes.xlsx' no es un Excel válido"); return pd.DataFrame()
    df = pd.read_excel(DATA_PATH).copy()
    df.columns = df.columns.str.strip()
    # tipados
    if "Última_visita" in df: df["Última_visita"] = pd.to_datetime(df["Última_visita"], errors="coerce")
    if "Valor"         in df: df["Valor"]         = pd.to_numeric(df["Valor"], errors="coerce").fillna(0)
    return df

def guardar_datos(df:pd.DataFrame):
    df.to_excel(DATA_PATH, index=False)

df = cargar_datos()         # <-- en memoria

# ─────────────────── 4. ENCABEZADO ───────────────────
st.image("logo.png", use_container_width=True)
st.markdown("<h2 style='text-align:center;'>👓 Sistema de Gestión BMA Ópticas</h2>", unsafe_allow_html=True)
st.markdown("<h4 style='text-align:center;color:gray;'>Cuidamos tus ojos, cuidamos de ti</h4>", unsafe_allow_html=True)
st.sidebar.title("Menú")

# ─────────────────── 5. NAVEGACIÓN ───────────────────
pagina = st.sidebar.radio("", ["🏠 Inicio","💰 Registrar venta","👁️ Pacientes"])

# ─────────────────── 6-A. INICIO ───────────────────
if pagina == "🏠 Inicio":
    st.subheader("Resumen rápido")
    if df.empty:
        st.info("Carga tu primera venta para comenzar 🙂")
    else:
        col1,col2,col3 = st.columns(3)
        col1.metric("Pacientes",         len(df["Rut"].unique()))
        col2.metric("Ventas registradas",len(df[df["Valor"]>0]))
        col3.metric("Total ventas",      f"${df['Valor'].sum():,.0f}")
        st.dataframe(df.tail(10), use_container_width=True)

# ─────────────────── 6-B. REGISTRAR VENTA ───────────────────
elif pagina == "💰 Registrar venta":
    st.subheader("➕ Registrar Venta")
    with st.form("venta", clear_on_submit=True):
        col1,col2 = st.columns(2)
        with col1:
            rut       = st.text_input("RUT* (con puntos y guion)")
            nombre    = st.text_input("Nombre*")
            edad      = st.number_input("Edad*", min_value=0, step=1)
            telefono  = st.text_input("Teléfono")
        with col2:
            tipo_lente= st.selectbox("Tipo de lente",["Monofocal","Bifocal","Progresivo"])
            armazon   = st.text_input("Armazón")
            valor     = st.number_input("Valor venta*", min_value=0, step=1000)
            forma_pg  = st.selectbox("Forma de pago",["Efectivo","Débito","Crédito","Transferencia"])
        # ópticos (opcionales)
        st.markdown("#### Datos ópticos (opcional)")
        cols = st.columns(6)
        etiquetas = ["OD_SPH","OD_CYL","OD_EJE","OI_SPH","OI_CYL","OI_EJE"]
        opticos = {lab: cols[i].text_input(lab) for i,lab in enumerate(etiquetas)}
        col_dp  = st.columns(3)
        dp_lejos  = col_dp[0].text_input("DP_Lejos")
        dp_cerca  = col_dp[1].text_input("DP_CERCA")
        add       = col_dp[2].text_input("ADD")
        guardar = st.form_submit_button("Guardar")

    if guardar:
        if not (rut and nombre and validar_rut(rut)):
            st.error("RUT inválido o campos obligatorios vacíos")
            st.stop()

        rut = rut.upper()
        nombre = capitalizar(nombre)
        venta  = {
            "Rut": rut, "Nombre": nombre, "Edad": edad, "Teléfono": telefono,
            "Tipo_Lente": tipo_lente, "Armazon": armazon, "Valor": valor,
            "FORMA_PAGO": forma_pg, "Última_visita": dt.date.today(),
            **opticos, "DP_Lejos": dp_lejos, "DP_CERCA": dp_cerca, "ADD": add
        }

        # ¿Paciente ya existe?
        existe = df["Rut"].astype(str).eq(rut).any()
        df.loc[len(df)] = venta           # añadimos la fila
        guardar_datos(df)                 # persistimos
        st.success("Venta (y paciente) guardados ✅")
        if existe:
            st.info("Se añadió la venta al historial del paciente existente.")
        else:
            st.info("Se creó un nuevo paciente.")
        st.experimental_rerun()

# ─────────────────── 6-C. PACIENTES & HISTORIAL ───────────────────
elif pagina == "👁️ Pacientes":
    st.subheader("👥 Historial de Pacientes y Ventas")
    if df.empty:
        st.warning("Aún no hay datos.")
        st.stop()

    # Búsqueda
    busc = st.text_input("Buscar (nombre o RUT)")
    datos = df.copy()
    if busc:
        datos = datos[
            datos["Nombre"].str.contains(busc, case=False, na=False) |
            datos["Rut"].astype(str).str.contains(busc, case=False, na=False)
        ]

    for rut, grp in datos.groupby("Rut"):
        pac = grp.iloc[-1]                                       # último registro
        with st.expander(f"👤 {pac['Nombre']} — {mascarar_rut(rut)}"):
            col1,col2 = st.columns([3,2])
            with col1: st.dataframe(
                grp[["Última_visita","Tipo_Lente","Armazon","Valor","FORMA_PAGO"]],
                use_container_width=True, height=200)
            # receta PDF
            if pac[COLUMNAS_OPT[0]]:       # si tiene receta
                pdf = generar_pdf_receta(pac)
                col2.download_button("Descargar última receta (PDF)",
                                    data=pdf,
                                    file_name=f"Receta_{pac['Nombre']}.pdf",
                                    mime="application/pdf")

# ─────────────────── FOOTER ───────────────────
st.sidebar.markdown("---")
st.sidebar.write("BMA Ópticas © 2025")
