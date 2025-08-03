import streamlit as st
import pandas as pd

# --- CONFIGURACIÓN DEL SISTEMA ---
st.set_page_config(page_title="BMA Ópticas", page_icon="👓", layout="wide")

# --- LOGO ---
st.image("Logotipo BmA.png", width=250)
st.title("👓 Sistema de Gestión BMA Ópticas")
st.markdown("### *Cuidamos tus ojos, cuidamos de ti.*")

# --- MENÚ LATERAL ---
menu = st.sidebar.radio("📂 Menú", ["🏠 Inicio", "👁 Pacientes", "💰 Ventas", "📊 Reportes", "⚠️ Alertas"])

# --- SECCIÓN INICIO ---
if menu == "🏠 Inicio":
    st.subheader("Bienvenido al Sistema BMA Ópticas")
    st.write("Aquí podrás gestionar pacientes, recetas, ventas y generar reportes automáticos.")

# --- PACIENTES ---
elif menu == "👁 Pacientes":
    st.subheader("📋 Base de Pacientes")
    st.dataframe(df)

    st.markdown("### 🔍 Buscar paciente")
    nombre = st.text_input("Escribe un nombre:")
    if nombre:
        resultado = df[df["Nombre"].str.contains(nombre, case=False)]
        st.write(resultado if not resultado.empty else "⚠️ Paciente no encontrado")

# --- VENTAS ---
elif menu == "💰 Ventas":
    st.subheader("💵 Ventas registradas")
    total = df["Valor"].sum()
    promedio = df["Valor"].mean()
    st.metric("💰 Total de ventas", f"${total:,.0f}".replace(",", "."))
    st.metric("💳 Ticket promedio", f"${promedio:,.0f}".replace(",", "."))

# --- REPORTES ---
elif menu == "📊 Reportes":
    st.subheader("📊 Reporte por tipo de lentes")
    por_tipo = df.groupby("Tipo_lentes")["Valor"].sum()
    for tipo, valor in por_tipo.items():
        st.write(f"- {tipo}: ${valor:,.0f}".replace(",", "."))

# --- ALERTAS ---
elif menu == "⚠️ Alertas":
    st.subheader("⚠️ Pacientes atrasados en control")
    st.info("Aquí aparecerán los pacientes que llevan 6+ meses sin control.")
