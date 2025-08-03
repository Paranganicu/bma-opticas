import pandas as pd
import streamlit as st
import datetime

# === CONFIGURACIÓN DEL SISTEMA ===
st.set_page_config(page_title="BMA Ópticas", page_icon="👓", layout="wide")

# === LOGO ===
try:
    st.image("logo.png", use_container_width=True)
except FileNotFoundError:
    st.warning("⚠️ Logo no encontrado (logo.png)")

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

# === CARGA DE BASE DE DATOS ===
@st.cache_data
def cargar_datos():
    """Función para cargar datos con cache para mejorar rendimiento"""
    try:
        df = pd.read_excel("Pacientes.xlsx")
        
        # Limpiar nombres de columnas (eliminar espacios)
        df.columns = df.columns.str.strip()
        
        # Convertir fechas
        if 'Última_visita' in df.columns:
            df['Última_visita'] = pd.to_datetime(df['Última_visita'], errors='coerce')
        
        # Convertir valores numéricos
        if 'Valor' in df.columns:
            df['Valor'] = pd.to_numeric(df['Valor'], errors='coerce')
        
        return df, True
    except FileNotFoundError:
        st.error("❌ No se encontró el archivo Pacientes.xlsx en el repositorio.")
        return pd.DataFrame(), False
    except Exception as e:
        st.error(f"❌ Error al cargar el archivo: {str(e)}")
        return pd.DataFrame(), False

# Cargar datos
df, datos_cargados = cargar_datos()

if datos_cargados:
    st.sidebar.success("✅ Base de datos cargada correctamente")
    st.sidebar.write(f"📊 Total de registros: {len(df)}")

# === MENÚ LATERAL ===
menu = st.sidebar.radio(
    "📁 Menú", 
    ["🏠 Inicio", "👁️ Pacientes", "💰 Ventas", "📊 Reportes", "⚠️ Alertas"]
)

# === PANTALLAS ===
if menu == "🏠 Inicio":
    st.markdown("### 🏠 Bienvenido al Sistema BMA Ópticas")
    st.write("Aquí podrás gestionar pacientes, recetas, ventas y generar reportes automáticos.")
    
    # Vista previa de la base de datos
    if datos_cargados:
        st.subheader("📂 Vista previa de la base de datos")
        st.write("✅ Columnas detectadas:", df.columns.tolist())
        st.dataframe(df.head())
    
elif menu == "👁️ Pacientes":
    st.subheader("📋 Listado de Pacientes")
    if datos_cargados and not df.empty:
        # Mostrar información básica de pacientes
        columnas_mostrar = ['Nombre', 'Rut', 'Edad', 'Teléfono', 'Última_visita', 'Tipo_Lente']
        df_pacientes = df[columnas_mostrar].copy()
        
        # Formatear fecha para mejor visualización
        if 'Última_visita' in df_pacientes.columns:
            df_pacientes['Última_visita'] = df_pacientes['Última_visita'].dt.strftime('%d/%m/%Y')
        
        st.dataframe(df_pacientes, use_container_width=True)
        
        # Filtros
        st.subheader("🔍 Filtros")
        col1, col2 = st.columns(2)
        
        with col1:
            tipos_lente = df['Tipo_Lente'].dropna().unique()
            filtro_tipo = st.selectbox("Filtrar por tipo de lente:", 
                                     ["Todos"] + list(tipos_lente))
        
        with col2:
            # Filtro por rango de edad
            if df['Edad'].notna().any():
                edad_min, edad_max = int(df['Edad'].min()), int(df['Edad'].max())
                rango_edad = st.slider("Rango de edad:", edad_min, edad_max, (edad_min, edad_max))
        
        # Aplicar filtros
        df_filtrado = df.copy()
        if filtro_tipo != "Todos":
            df_filtrado = df_filtrado[df_filtrado['Tipo_Lente'] == filtro_tipo]
        
        if 'rango_edad' in locals():
            df_filtrado = df_filtrado[
                (df_filtrado['Edad'] >= rango_edad[0]) & 
                (df_filtrado['Edad'] <= rango_edad[1])
            ]
        
        if len(df_filtrado) != len(df):
            st.write(f"📊 Mostrando {len(df_filtrado)} de {len(df)} pacientes")
            df_filtrado_mostrar = df_filtrado[columnas_mostrar].copy()
            if 'Última_visita' in df_filtrado_mostrar.columns:
                df_filtrado_mostrar['Última_visita'] = df_filtrado['Última_visita'].dt.strftime('%d/%m/%Y')
            st.dataframe(df_filtrado_mostrar, use_container_width=True)
    else:
        st.warning("⚠️ No hay datos para mostrar.")

elif menu == "💰 Ventas":
    st.subheader("💰 Reporte de Caja")
    if datos_cargados and not df.empty:
        # Filtrar valores válidos
        df_ventas = df[df['Valor'].notna() & (df['Valor'] > 0)].copy()
        
        if not df_ventas.empty:
            # Métricas principales
            total_ventas = df_ventas['Valor'].sum()
            ticket_promedio = df_ventas['Valor'].mean()
            num_ventas = len(df_ventas)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total de Ventas", f"${total_ventas:,.0f}")
            with col2:
                st.metric("Ticket Promedio", f"${ticket_promedio:,.0f}")
            with col3:
                st.metric("Número de Ventas", num_ventas)
            
            # Análisis por forma de pago
            st.subheader("💳 Ventas por Forma de Pago")
            if 'FORMA_PAGO' in df_ventas.columns:
                ventas_pago = df_ventas.groupby('FORMA_PAGO')['Valor'].agg(['sum', 'count']).reset_index()
                ventas_pago.columns = ['Forma_Pago', 'Total_Ventas', 'Cantidad']
                ventas_pago['Porcentaje'] = (ventas_pago['Total_Ventas'] / total_ventas * 100).round(1)
                
                col1, col2 = st.columns(2)
                with col1:
                    st.dataframe(ventas_pago, use_container_width=True)
                with col2:
                    st.bar_chart(ventas_pago.set_index('Forma_Pago')['Total_Ventas'])
            
            # Ventas por mes
            st.subheader("📅 Ventas por Período")
            if 'Última_visita' in df_ventas.columns:
                df_ventas['Mes'] = df_ventas['Última_visita'].dt.to_period('M')
                ventas_mes = df_ventas.groupby('Mes')['Valor'].sum().reset_index()
                ventas_mes['Mes'] = ventas_mes['Mes'].astype(str)
                
                st.line_chart(ventas_mes.set_index('Mes')['Valor'])
        else:
            st.warning("⚠️ No hay ventas válidas para mostrar.")
    else:
        st.warning("⚠️ No hay datos de ventas.")

elif menu == "📊 Reportes":
    st.subheader("📊 Reporte por Tipo de Lentes")
    if datos_cargados and not df.empty:
        # Reporte por tipo de lente
        df_reportes = df[df['Valor'].notna() & (df['Valor'] > 0)].copy()
        
        if not df_reportes.empty:
            ventas_tipo = df_reportes.groupby('Tipo_Lente').agg({
                'Valor': ['sum', 'mean', 'count']
            }).round(0)
            
            ventas_tipo.columns = ['Total_Ventas', 'Promedio', 'Cantidad']
            ventas_tipo = ventas_tipo.reset_index().sort_values('Total_Ventas', ascending=False)
            
            col1, col2 = st.columns(2)
            with col1:
                st.write("### 📈 Resumen por Tipo de Lente")
                st.dataframe(ventas_tipo, use_container_width=True)
            
            with col2:
                st.write("### 📊 Gráfico de Ventas")
                st.bar_chart(ventas_tipo.set_index('Tipo_Lente')['Total_Ventas'])
            
            # Análisis por armazón
            st.subheader("🕶️ Análisis por Armazón")
            if 'Armazon' in df_reportes.columns:
                armazon_stats = df_reportes.groupby('Armazon').agg({
                    'Valor': ['sum', 'count'],
                    'Tipo_Lente': lambda x: ', '.join(x.unique())
                }).round(0)
                
                armazon_stats.columns = ['Total_Ventas', 'Cantidad', 'Tipos_Lente']
                armazon_stats = armazon_stats.reset_index().sort_values('Total_Ventas', ascending=False)
                
                st.dataframe(armazon_stats, use_container_width=True)
        else:
            st.warning("⚠️ No hay datos válidos para el reporte.")
    
    # === RECETAS ÓPTICAS ===
    st.subheader("📄 Recetas Ópticas")
    if datos_cargados and not df.empty:
        # Filtrar solo pacientes con datos ópticos
        columnas_opticas = ['OD_SPH', 'OD_CYL', 'OD_EJE', 'OI_SPH', 'OI_CYL', 'OI_EJE']
        df_recetas = df.dropna(subset=columnas_opticas, how='all').copy()
        
        if not df_recetas.empty:
            for _, row in df_recetas.iterrows():
                st.write(f"**👤 {row['Nombre']}** – {row['Rut']} – Edad: {row['Edad']} años")
                
                # Mostrar prescripción
                col1, col2 = st.columns(2)
                with col1:
                    st.text(f"OD: {row.get('OD_SPH', 'N/A')} {row.get('OD_CYL', 'N/A')} x {row.get('OD_EJE', 'N/A')}")
                with col2:
                    st.text(f"OI: {row.get('OI_SPH', 'N/A')} {row.get('OI_CYL', 'N/A')} x {row.get('OI_EJE', 'N/A')}")
                
                # Información adicional
                info_adicional = []
                if pd.notna(row.get('DP_Lejos')):
                    info_adicional.append(f"DP Lejos: {row['DP_Lejos']}")
                if pd.notna(row.get('DP_CERCA')):
                    info_adicional.append(f"DP Cerca: {row['DP_CERCA']}")
                if pd.notna(row.get('ADD')):
                    info_adicional.append(f"ADD: {row['ADD']}")
                
                if info_adicional:
                    st.text(" | ".join(info_adicional))
                
                # Detalles del producto
                st.text(f"Tipo: {row['Tipo_Lente']} | Armazón: {row.get('Armazon', 'N/A')} | Cristales: {row.get('Tipo_Cxs', 'N/A')}")
                st.markdown("---")
        else:
            st.info("ℹ️ No hay pacientes con prescripciones ópticas registradas.")
    else:
        st.warning("⚠️ No hay recetas disponibles.")

elif menu == "⚠️ Alertas":
    st.subheader("⚠️ Alertas del Sistema")
    
    if datos_cargados and not df.empty:
        alertas = []
        
        # Alerta: Pacientes sin control reciente
        fecha_limite = datetime.datetime.now() - datetime.timedelta(days=365)
        pacientes_sin_control = df[df['Última_visita'] < fecha_limite]
        
        if not pacientes_sin_control.empty:
            alertas.append({
                'tipo': 'warning',
                'mensaje': f"📅 {len(pacientes_sin_control)} pacientes sin control en más de 12 meses",
                'detalle': pacientes_sin_control[['Nombre', 'Rut', 'Última_visita']].copy()
            })
        
        # Alerta: Ventas con valores inusuales
        if df['Valor'].notna().any():
            ventas_altas = df[df['Valor'] > df['Valor'].quantile(0.95)]
            if not ventas_altas.empty:
                alertas.append({
                    'tipo': 'info',
                    'mensaje': f"💰 {len(ventas_altas)} ventas con valores superiores al promedio",
                    'detalle': ventas_altas[['Nombre', 'Valor', 'Tipo_Lente']].copy()
                })
        
        # Alerta: Pacientes mayores
        pacientes_mayores = df[df['Edad'] > 65]
        if not pacientes_mayores.empty:
            alertas.append({
                'tipo': 'info',
                'mensaje': f"👴 {len(pacientes_mayores)} pacientes mayores de 65 años (requieren atención especial)",
                'detalle': pacientes_mayores[['Nombre', 'Edad', 'Última_visita']].copy()
            })
        
        # Mostrar alertas
        if alertas:
            for alerta in alertas:
                if alerta['tipo'] == 'warning':
                    st.warning(alerta['mensaje'])
                else:
                    st.info(alerta['mensaje'])
                
                # Mostrar detalles en expander
                with st.expander("Ver detalles"):
                    st.dataframe(alerta['detalle'], use_container_width=True)
        else:
            st.success("✅ No hay alertas activas en el sistema")
    else:
        st.info("ℹ️ Carga la base de datos para ver alertas del sistema.")
