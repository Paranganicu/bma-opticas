import pandas as pd
import streamlit as st

# === CARGA DE BASE DE DATOS ===
try:
    df = pd.read_excel("Pacientes.xlsx")

    st.subheader("📂 Vista previa de la base de datos")
    st.write("✅ Columnas detectadas:", df.columns.tolist())
    st.dataframe(df.head())

except FileNotFoundError:
    st.error("❌ No se encontró el archivo Pacientes.xlsx en el repositorio.")
    df = pd.DataFrame()  # DataFrame vacío para evitar errores

# === CONFIGURACIÓN DEL SISTEMA ===
st.set_page_config(page_title="BMA Ópticas", page_icon="👓", layout="wide")

# === LOGO ===
st.image("logo.png", use_container_width=True)

# === TÍTULO PRINCIPAL ===
st.markdown(
    "<h2 style='text-align: center;'>👓 Sistema de Gestión BMA Ópticas</h2>",
    unsafe_allow_html=True
)

# === SUBTÍTULO ===
st.markdown(
    "<h3 style='text-align: center; color: gray;'>Cuidamos tus ojos, cuidamos de ti.</h3>",
    unsafe_allow_html=True
)

# === MENÚ LATERAL ===
menu = st.sidebar.radio("📁 Menú", ["🏠 Inicio", "👁️ Pacientes", "💰 Ventas", "📊 Reportes", "⚠️ Alertas"])

# === PANTALLAS ===
if menu == "🏠 Inicio":
    st.markdown("### 🏠 Bienvenido al Sistema BMA Ópticas")
    st.write("Aquí podrás gestionar pacientes, recetas, ventas y generar reportes automáticos.")

elif menu == "👁️ Pacientes":
    st.subheader("📋 Listado de Pacientes")
    if not df.empty:
        st.dataframe(df[["Nombre", "Rut", "Teléfono", "Última_visita", "Tipo_Lente"]])
    else:
        st.warning("⚠️ No hay datos para mostrar.")

elif menu == "💰 Ventas":
    st.subheader("💰 Reporte de Caja")
    if not df.empty:
        total_ventas = df["Valor"].sum()
        ticket_promedio = df["Valor"].mean()
        st.metric("Total de Ventas", f"${total_ventas:,.0f}")
        st.metric("Ticket Promedio", f"${ticket_promedio:,.0f}")
    else:
        st.warning("⚠️ No hay datos de ventas.")

elif menu == "📊 Reportes":
    st.subheader("📊 Reporte por Tipo de Lentes")
    if not df.empty:
        if "Tipo_Lente" in df.columns:
            ventas_por_tipo = df.groupby("Tipo_Lente")["Valor"].sum()
            st.bar_chart(ventas_por_tipo)
            st.write("### 📈 Ventas por tipo de lente")
            st.write(ventas_por_tipo)
        else:
            st.warning("⚠️ La columna 'Tipo_Lente' no existe en la base de datos.")
    else:
        st.warning("⚠️ No hay datos para reportar.")

    st.subheader("📄 Recetas Ópticas")
    if not df.empty:
        for i, row in df.iterrows():
            st.write(f"**👤 {row['Nombre']}** – {row['Rut']}")
            st.text(f" OD: {row['OD_SPH']}  {row['OD_CYL']}  x {row['OD_EJE']}")
            st.text(f" OI: {row['OI_SPH']}  {row['OI_CYL']}  x {row['OI_EJE']}")
            st.text(f" DP Lejos: {row['DP_Lejos']}   DP Cerca: {row['DP_CERCA']}   ADD: {row['ADD']}")
            st.markdown("---")
    else:
        st.warning("⚠️ No hay recetas disponibles.")

elif menu == "⚠️ Alertas":
    st.subheader("⚠️ Alertas del Sistema")
    st.info("Aquí aparecerán alertas importantes, como pacientes sin control reciente.")
