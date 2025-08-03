Para darte el código completo con la corrección que te mencioné, he integrado la solución directamente en el archivo original.

Este código resuelve el problema potencial con la variable `rango_edad` y también ajusta la forma en que se muestran las fechas después de aplicar los filtros, asegurándose de que la aplicación sea más robusta.

**Aquí tienes el código completo y corregido:**

```python
import pandas as pd
import streamlit as st
import datetime

# === CONFIGURACIÓN GENERAL ===
st.set_page_config(page_title="BMA Ópticas", page_icon="👓", layout="wide")

# === FUNCIÓN: Cargar datos ===
@st.cache_data
def cargar_datos():
    """Carga la base de datos de pacientes con limpieza básica"""
    try:
        df = pd.read_excel("Pacientes.xlsx")
        df.columns = df.columns.str.strip()  # limpia espacios en nombres de columnas

        if 'Última_visita' in df.columns:
            df['Última_visita'] = pd.to_datetime(df['Última_visita'], errors='coerce')
        if 'Valor' in df.columns:
            df['Valor'] = pd.to_numeric(df['Valor'], errors='coerce')

        return df
    except FileNotFoundError:
        st.error("❌ No se encontró el archivo Pacientes.xlsx en el repositorio.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Error al cargar el archivo: {str(e)}")
        return pd.DataFrame()

# === FUNCIÓN: Logo y título ===
def mostrar_header():
    try:
        st.image("logo.png", use_container_width=True)
    except FileNotFoundError:
        st.warning("⚠️ Logo no encontrado (logo.png)")

    st.markdown(
        "<h2 style='text-align: center;'>👓 Sistema de Gestión BMA Ópticas</h2>",
        unsafe_allow_html=True
    )
    st.markdown(
        "<h3 style='text-align: center; color: gray;'>Cuidamos tus ojos, cuidamos de ti.</h3>",
        unsafe_allow_html=True
    )

# === PANTALLAS ===
def pantalla_inicio(df):
    st.markdown("### 🏠 Bienvenido al Sistema BMA Ópticas")
    st.write("Aquí podrás gestionar pacientes, recetas, ventas y generar reportes automáticos.")
    if not df.empty:
        st.subheader("📂 Vista previa de la base de datos")
        st.write("✅ Columnas detectadas:", df.columns.tolist())
        st.dataframe(df.head())

def pantalla_pacientes(df):
    st.subheader("📋 Listado de Pacientes")
    if df.empty:
        st.warning("⚠️ No hay datos para mostrar.")
        return

    columnas = ['Nombre', 'Rut', 'Edad', 'Teléfono', 'Última_visita', 'Tipo_Lente']
    df_pacientes = df[columnas].copy()

    # Formatear fecha
    if 'Última_visita' in df_pacientes.columns:
        df_pacientes['Última_visita'] = df_pacientes['Última_visita'].dt.strftime('%d/%m/%Y')

    st.dataframe(df_pacientes, use_container_width=True)

    # === Filtros ===
    st.subheader("🔍 Filtros")
    col1, col2 = st.columns(2)

    # Inicializamos rango_edad con un valor por defecto
    rango_edad = None

    with col1:
        tipos_lente = df['Tipo_Lente'].dropna().unique()
        filtro_tipo = st.selectbox("Filtrar por tipo de lente:", ["Todos"] + list(tipos_lente))

    with col2:
        if df['Edad'].notna().any():
            edad_min, edad_max = int(df['Edad'].min()), int(df['Edad'].max())
            rango_edad = st.slider("Rango de edad:", edad_min, edad_max, (edad_min, edad_max))

    # Aplicar filtros
    df_filtrado = df.copy()
    if filtro_tipo != "Todos":
        df_filtrado = df_filtrado[df_filtrado['Tipo_Lente'] == filtro_tipo]

    # Ahora verificamos si rango_edad no es None
    if rango_edad is not None:
        df_filtrado = df_filtrado[(df_filtrado['Edad'] >= rango_edad[0]) & (df_filtrado['Edad'] <= rango_edad[1])]

    # Mostrar filtrado
    if len(df_filtrado) != len(df):
        st.write(f"📊 Mostrando {len(df_filtrado)} de {len(df)} pacientes")
        # Aseguramos que la columna de fecha esté en formato de fecha antes de formatear a string
        if 'Última_visita' in df_filtrado.columns:
            df_filtrado['Última_visita'] = pd.to_datetime(df_filtrado['Última_visita'])
            df_filtrado['Última_visita'] = df_filtrado['Última_visita'].dt.strftime('%d/%m/%Y')
        st.dataframe(df_filtrado[columnas], use_container_width=True)

def pantalla_ventas(df):
    st.subheader("💰 Reporte de Caja")
    if df.empty:
        st.warning("⚠️ No hay datos de ventas.")
        return

    df_ventas = df[df['Valor'].notna() & (df['Valor'] > 0)]
    if df_ventas.empty:
        st.warning("⚠️ No hay ventas válidas para mostrar.")
        return

    total = df_ventas['Valor'].sum()
    promedio = df_ventas['Valor'].mean()
    num = len(df_ventas)

    col1, col2, col3 = st.columns(3)
    col1.metric("Total de Ventas", f"${total:,.0f}")
    col2.metric("Ticket Promedio", f"${promedio:,.0f}")
    col3.metric("Número de Ventas", num)

    st.subheader("💳 Ventas por Forma de Pago")
    if 'FORMA_PAGO' in df.columns:
        ventas_pago = df.groupby('FORMA_PAGO')['Valor'].sum()
        st.bar_chart(ventas_pago)

def pantalla_reportes(df):
    st.subheader("📊 Reporte por Tipo de Lentes")
    if df.empty:
        st.warning("⚠️ No hay datos para reportar.")
        return

    df_reportes = df[df['Valor'].notna() & (df['Valor'] > 0)]
    if df_reportes.empty:
        st.warning("⚠️ No hay datos válidos para el reporte.")
        return

    # Reporte por tipo de lente
    ventas_tipo = df_reportes.groupby('Tipo_Lente')['Valor'].sum()
    st.bar_chart(ventas_tipo)
    st.dataframe(ventas_tipo)

    # === Recetas Ópticas ===
    st.subheader("📄 Recetas Ópticas")
    columnas_opticas = ['OD_SPH', 'OD_CYL', 'OD_EJE', 'OI_SPH', 'OI_CYL', 'OI_EJE']
    df_recetas = df.dropna(subset=columnas_opticas, how='all')

    if df_recetas.empty:
        st.info("ℹ️ No hay pacientes con prescripciones ópticas registradas.")
        return

    for _, row in df_recetas.iterrows():
        st.write(f"**👤 {row['Nombre']}** – {row['Rut']} – Edad: {row['Edad']} años")
        st.text(f"OD: {row['OD_SPH']} {row['OD_CYL']} x {row['OD_EJE']}")
        st.text(f"OI: {row['OI_SPH']} {row['OI_CYL']} x {row['OI_EJE']}")
        st.text(f"DP Lejos: {row.get('DP_Lejos', 'N/A')} | DP Cerca: {row.get('DP_CERCA', 'N/A')} | ADD: {row.get('ADD', 'N/A')}")
        st.markdown("---")

def pantalla_alertas(df):
    st.subheader("⚠️ Alertas del Sistema")
    if df.empty:
        st.info("ℹ️ Carga la base de datos para ver alertas del sistema.")
        return

    alertas = []

    # Pacientes sin control en 12 meses
    if 'Última_visita' in df.columns:
        fecha_limite = datetime.datetime.now() - datetime.timedelta(days=365)
        sin_control = df[df['Última_visita'] < fecha_limite]
        if not sin_control.empty:
            st.warning(f"📅 {len(sin_control)} pacientes sin control en más de 12 meses")
            with st.expander("Ver lista"):
                st.dataframe(sin_control[['Nombre', 'Rut', 'Última_visita']])

    # Ventas altas
    if 'Valor' in df.columns:
        ventas_altas = df[df['Valor'] > df['Valor'].quantile(0.95)]
        if not ventas_altas.empty:
            st.info(f"💰 {len(ventas_altas)} ventas con valores superiores al promedio")
            with st.expander("Ver ventas altas"):
                st.dataframe(ventas_altas[['Nombre', 'Valor', 'Tipo_Lente']])

# === EJECUCIÓN APP ===
mostrar_header()
df = cargar_datos()

menu = st.sidebar.radio("📁 Menú", ["🏠 Inicio", "👁️ Pacientes", "💰 Ventas", "📊 Reportes", "⚠️ Alertas"])

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
```
