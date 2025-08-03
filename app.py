import pandas as pd
import streamlit as st

# === BASE DE DATOS ===
try: 
    df = pd.read_excel("Pacientes.xlsx")
    st.subheader("📋 Vista previa de la base de datos")
    st.write("✅ Columnas detectadas:", df.columns.tolist())
    st.dataframe(df.head())

except FileNotFoundError:
    st.error("📂 No se encontró el archivo Pacientes.xlsx en el repositorio.")
    df = pd.DataFrame()  # DataFrame vacío para evitar errores 

# --- CONFIGURACIÓN DEL SISTEMA ---
st.set_page_config(page_title="BMA Ópticas", page_icon="👓", layout="wide")

# --- LOGO ---
st.image("logo.png", use_container_width=True)# --- TÍTULO PRINCIPAL ---
st.markdown(
    "<h2 style='text-align: center;'>👓 Sistema de Gestión BMA Ópticas</h2>", 
    unsafe_allow_html=True
)

# --- SUBTÍTULO ---
st.markdown(
    "<h3 style='text-align: center; color: gray;'>Cuidamos tus ojos, cuidamos de ti.</h3>", 
    unsafe_allow_html=True
)
# --- MENÚ PRINCIPAL ---
menu = st.sidebar.radio("📂 Menú", ["🏠 Inicio", "👁 Pacientes", "💰 Ventas", "📊 Reportes", "⚠️ Alertas"])

# --- PANTALLAS ---
if menu == "🏠 Inicio":
    st.title("🏠 Inicio")
    st.write("Bienvenido al **Sistema de Gestión BMA Ópticas**")

elif menu == "👁 Pacientes":
    st.title("👁 Pacientes")
    st.write("Aquí podrás gestionar la base de datos de pacientes.")

elif menu == "💰 Ventas":
    st.title("💰 Ventas")
    st.write("Aquí se registran y visualizan las ventas.")

elif menu == "📊 Reportes":
    st.title("📊 Reportes")
    st.write("Aquí podrás generar reportes automáticos.")

elif menu == "⚠️ Alertas":
    st.title("⚠️ Alertas")
    st.write("Aquí aparecerán las alertas importantes.")
