import os
import re
import uuid
import logging
import datetime as dt
from io import BytesIO
from typing import Dict, Any, Optional

import pandas as pd
import streamlit as st
from html import escape
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import magic  # linux-only; en Windows & Streamlit Cloud funciona
from reportlab.lib.units import mm

# ========== CONFIGURACIÓN BÁSICA ==========
st.set_page_config(page_title="BMA Ópticas", page_icon="👓", layout="wide")
logging.basicConfig(
    filename="app.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ========== CONSTANTES ==========
COLUMNAS_OPTICAS = [
    "OD_SPH", "OD_CYL", "OD_EJE",
    "OI_SPH", "OI_CYL", "OI_EJE",
    "DP_Lejos", "DP_CERCA", "ADD"
]
MIME_VALIDOS = [
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
]

# ========== VALIDACIONES ==========
def validar_rut_completo(rut: str) -> bool:
    """Valida RUT chileno completo (cuerpo + DV)"""
    try:
        rut = rut.upper().replace(".", "").replace("-", "")
        if not re.match(r"^[0-9]{7,8}[0-9K]$", rut):
            return False

        cuerpo, dv = rut[:-1], rut[-1]
        suma, multiplo = 0, 2
        for c in reversed(cuerpo):
            suma += int(c) * multiplo
            multiplo = multiplo + 1 if multiplo < 7 else 2

        dv_esperado = 11 - (suma % 11)
        dv_esperado = {10: "K", 11: "0"}.get(dv_esperado, str(dv_esperado))
        return dv == dv_esperado
    except Exception as e:
        logging.error(f"Error validando RUT {rut}: {e}")
        return False


def enmascarar_rut(rut: str) -> str:
    """Enmascara parcialmente el RUT"""
    if not isinstance(rut, str) or "-" not in rut:
        return rut
    cuerpo, dv = rut.split("-")
    cuerpo = f"{cuerpo[:-4]}****" if len(cuerpo) > 4 else cuerpo
    return f"{cuerpo}-{dv}"


def es_excel_valido(path: str) -> bool:
    try:
        return magic.from_file(path, mime=True) in MIME_VALIDOS
    except Exception as e:
        logging.error(f"Validación MIME: {e}")
        return False

# ========== CARGA DE DATOS ==========
@st.cache_data(ttl=3600, hash_funcs={pd.DataFrame: lambda _: None})
def cargar_datos() -> pd.DataFrame:
    if not os.path.exists("Pacientes.xlsx"):
        st.error("❌ 'Pacientes.xlsx' no encontrado")
        return pd.DataFrame()

    if not es_excel_valido("Pacientes.xlsx"):
        st.error("❌ Archivo no es Excel válido")
        return pd.DataFrame()

    try:
        df = pd.read_excel("Pacientes.xlsx").copy()
        df.columns = df.columns.str.strip()

        if "Rut" in df.columns:
            df["Rut_Válido"] = df["Rut"].apply(validar_rut_completo)
            if not df["Rut_Válido"].all():
                st.warning("⚠️ Hay RUTs inválidos en la base")

        if "Última_visita" in df.columns:
            df["Última_visita"] = pd.to_datetime(
                df["Última_visita"], errors="coerce"
            )

        if "Valor" in df.columns:
            df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce").fillna(0)

        for col in COLUMNAS_OPTICAS:
            if col in df.columns:
                df[col] = df[col].fillna("").astype(str).str.strip()

        logging.info(f"Datos cargados: {len(df)} registros")
        return df
    except Exception as e:
        st.error(f"❌ Error crítico al cargar datos: {e}")
        logging.critical(e, exc_info=True)
        return pd.DataFrame()

# ========== GENERACIÓN DE PDF ==========
def generar_pdf_receta(paciente: Dict[str, Any]) -> BytesIO:
    buffer = BytesIO()
    tmp_name = f"temp_{uuid.uuid4()}.pdf"

    try:
        c = canvas.Canvas(tmp_name, pagesize=letter)
        c.setTitle(f"Receta - {escape(str(paciente.get('Nombre', '')))}")

        # Encabezado
        c.setFont("Helvetica-Bold", 16)
        c.drawString(72, 750, "BMA Ópticas - Receta Óptica")

        # Paciente
        c.setFont("Helvetica", 12)
        c.drawString(72, 730, f"Paciente: {escape(paciente.get('Nombre', ''))}")
        c.drawString(72, 712, f"RUT: {enmascarar_rut(paciente.get('Rut', ''))}")
        c.drawString(400, 712, dt.datetime.now().strftime("%d/%m/%Y"))

        # Tabla
        y = 680
        c.setFont("Helvetica-Bold", 12)
        c.drawString(72, y, "OD / OI")
        c.drawString(180, y, "ESF  CIL  EJE")
        y -= 20
        c.setFont("Helvetica", 12)
        c.drawString(
            72, y,
            f"OD: {paciente.get('OD_SPH','')}  {paciente.get('OD_CYL','')}  {paciente.get('OD_EJE','')}"
        )
        y -= 20
        c.drawString(
            72, y,
            f"OI: {paciente.get('OI_SPH','')}  {paciente.get('OI_CYL','')}  {paciente.get('OI_EJE','')}"
        )

        # Extra
        y -= 30
        extras = []
        if paciente.get("DP_Lejos"): extras.append(f"DP Lejos: {paciente['DP_Lejos']}")
        if paciente.get("DP_CERCA"): extras.append(f"DP Cerca: {paciente['DP_CERCA']}")
        if paciente.get("ADD"): extras.append(f"ADD: {paciente['ADD']}")
        for ex in extras:
            c.drawString(72, y, ex)
            y -= 18

        # Firma
        c.line(400, 100, 520, 100)
        c.drawString(430, 85, "Firma Óptico")

        c.save()

        with open(tmp_name, "rb") as f:
            buffer.write(f.read())
        os.remove(tmp_name)
        buffer.seek(0)
        return buffer
    except Exception as e:
        logging.error(f"PDF error: {e}", exc_info=True)
        return BytesIO()

# ========== INTERFAZ GRÁFICA ==========
def mostrar_header():
    st.image("logo.png", use_column_width=True)
    st.markdown(
        "<h2 style='text-align:center;'>👓 Sistema de Gestión BMA Ópticas</h2>",
        unsafe_allow_html=True
    )
    st.markdown(
        "<h4 style='text-align:center;color:gray;'>Cuidamos tus ojos, cuidamos de ti</h4>",
        unsafe_allow_html=True
    )

# ---------- PANTALLAS ----------
def pantalla_inicio(df: pd.DataFrame):
    st.header("🏠 Inicio")
    if df.empty:
        st.info("Carga un 'Pacientes.xlsx' para comenzar")
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("Total pacientes", len(df))
    col2.metric(
        "Pacientes con receta",
        df[COLUMNAS_OPTICAS[0]].notna().sum()
    )
    col3.metric("Ventas totales", f"${df['Valor'].sum():,.0f}")
    st.markdown("---")
    st.dataframe(df.head())

def pantalla_pacientes(df: pd.DataFrame):
    st.header("👁️ Pacientes")
    if df.empty:
        st.warning("No hay datos")
        return

    # ---------- FILTROS ----------
    with st.expander("Filtros"):
        busqueda = st.text_input("Nombre, RUT o Teléfono")
        tipos = ["Todos"] + sorted(df["Tipo_Lente"].dropna().unique())
        tipo = st.selectbox("Tipo lente", tipos)
        armazones = ["Todos"] + sorted(df["Armazon"].dropna().unique())
        armazon = st.selectbox("Armazón", armazones)
        edad_min, edad_max = int(df["Edad"].min()), int(df["Edad"].max())
        r_edad = st.slider("Edad",
                           edad_min, edad_max,
                           (edad_min, edad_max))

    # ---------- APLICAR FILTROS ----------
    df_f = df.copy()

    if busqueda:
        mask = (
            df_f["Nombre"].str.contains(busqueda, case=False, na=False) |
            df_f["Rut"].astype(str).str.contains(busqueda, case=False, na=False) |
            df_f["Teléfono"].astype(str).str.contains(busqueda, case=False, na=False)
        )
        df_f = df_f[mask]

    if tipo != "Todos":
        df_f = df_f[df_f["Tipo_Lente"] == tipo]

    if armazon != "Todos":
        df_f = df_f[df_f["Armazon"] == armazon]

    df_f = df_f[
        (df_f["Edad"] >= r_edad[0]) &
        (df_f["Edad"] <= r_edad[1])
    ]

    st.success(f"{len(df_f)} resultados")
    st.dataframe(df_f)

def pantalla_ventas(df: pd.DataFrame):
    st.header("💰 Ventas")
    ventas = df[df["Valor"] > 0]
    if ventas.empty:
        st.info("No hay ventas")
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("Total", f"${ventas['Valor'].sum():,.0f}")
    col2.metric("Ticket medio", f"${ventas['Valor'].mean():,.0f}")
    col3.metric("Transacciones", len(ventas))

def pantalla_reportes(df: pd.DataFrame):
    st.header("📊 Reportes")
    if df.empty:
        st.warning("No hay datos")
        return

    # Ventas por tipo de lente
    ventas = df[df["Valor"] > 0]
    if not ventas.empty:
        por_tipo = ventas.groupby("Tipo_Lente")["Valor"].sum()
        st.bar_chart(por_tipo)

    # Recetas + PDF
    st.subheader("Recetas")
    con_receta = df[df[COLUMNAS_OPTICAS[0]].notna()]
    for _, pac in con_receta.iterrows():
        with st.expander(f"{pac['Nombre']} – {enmascarar_rut(pac['Rut'])}"):
            st.write(pac[COLUMNAS_OPTICAS[:6]].to_frame().T)
            if st.button("📄 PDF", key=pac["Rut"]):
                pdf = generar_pdf_receta(pac)
                st.download_button(
                    "Descargar",
                    data=pdf,
                    file_name=f"Receta_{pac['Nombre']}.pdf",
                    mime="application/pdf"
                )

def pantalla_alertas(df: pd.DataFrame):
    st.header("⚠️ Alertas")
    if df.empty:
        st.info("No hay datos")
        return

    sin_control = df[
        df["Última_visita"] < dt.datetime.now() - dt.timedelta(days=365)
    ]
    if not sin_control.empty:
        st.warning(f"{len(sin_control)} pacientes sin control > 1 año")
        st.dataframe(sin_control[["Nombre", "Última_visita", "Teléfono"]])

# ========== MAIN ==========
def main():
    mostrar_header()
    with st.spinner("Cargando datos..."):
        df = cargar_datos()

    menu = st.sidebar.radio(
        "Menú",
        ["🏠 Inicio", "👁️ Pacientes", "💰 Ventas", "📊 Reportes", "⚠️ Alertas"]
    )

    if menu == "🏠 Inicio":
        pantalla_inicio(df)
    elif menu == "👁️ Pacientes":
        pantalla_pacientes(df)
    elif menu == "💰 Ventas":
        pantalla_ventas(df)
    elif menu == "📊 Reportes":
        pantalla_reportes(df)
    elif menu == "⚠️ Alertas":
        pantalla_alertas(df)

    st.sidebar.markdown("---")
    st.sidebar.write("BMA Ópticas © 2025")

if __name__ == "__main__":
    main()
