import pandas as pd
import streamlit as st
import datetime

# --- CONFIGURACIÓN DE LA APP ---
st.set_page_config(page_title="Gestión de Pacientes BMA Ópticas", page_icon="👓", layout="wide")

# --- FUNCIÓN: CARGAR DATOS ---
@st.cache_data
def cargar_datos():
    """Carga y limpia la base de datos de pacientes desde un archivo Excel."""
    try:
        df = pd.read_excel("Pacientes.xlsx")
        df.columns = df.columns.str.strip().str.replace(' ', '_')  # Limpiar y estandarizar nombres de columnas

        # Convertir columnas a tipos de datos correctos
        if 'Última_visita' in df.columns:
            df['Última_visita'] = pd.to_datetime(df['Última_visita'], errors='coerce')
        if 'Teléfono' in df.columns:
            df['Teléfono'] = df['Teléfono'].astype(str)
        
        return df
    except FileNotFoundError:
        st.error("❌ Error: No se encontró el archivo Pacientes.xlsx.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Error al cargar los datos: {e}")
        return pd.DataFrame()

# --- HEADER DE LA APLICACIÓN ---
def mostrar_header():
    st.markdown("<h1 style='text-align: center;'>👓 BMA Ópticas - Histórico de Pacientes</h1>", unsafe_allow_html=True)
    st.write("---")

# --- PANTALLAS DE LA APP ---
def pantalla_buscar_paciente(df):
    st.header("🔍 Buscar Paciente y Ver Historial")
    query = st.text_input("Ingresa el nombre o teléfono del paciente:", "")
    
    if query:
        # Convertir a minúsculas para una búsqueda insensible a mayúsculas
        df['Nombre_lower'] = df['Nombre'].str.lower()
        df['Teléfono_str'] = df['Teléfono'].astype(str)

        resultados = df[
            df['Nombre_lower'].str.contains(query.lower(), na=False) |
            df['Teléfono_str'].str.contains(query, na=False)
        ]
        
        if not resultados.empty:
            for _, row in resultados.iterrows():
                with st.expander(f"👤 **{row['Nombre']}** - Teléfono: {row['Teléfono']}"):
                    st.markdown("#### Datos de la última visita:")
                    st.write(f"- **Última visita:** {row['Última_visita'].strftime('%d/%m/%Y') if pd.notna(row['Última_visita']) else 'N/A'}")
                    st.write(f"- **Tipo de Lente:** {row.get('Tipo_Lente', 'N/A')}")
                    st.write(f"- **Armazón:** {row.get('Armazon', 'N/A')}")
                    st.write(f"- **Valor Pagado:** ${row.get('Valor', 'N/A'):,.0f}" if pd.notna(row.get('Valor')) else "- **Valor Pagado:** N/A")

                    st.markdown("#### Receta Óptica:")
                    st.write("##### **Ojo Derecho (OD):**")
                    st.text(f"  Esfera: {row.get('OD_SPH', 'N/A')}, Cilindro: {row.get('OD_CYL', 'N/A')}, Eje: {row.get('OD_EJE', 'N/A')}")
                    st.write("##### **Ojo Izquierdo (OI):**")
                    st.text(f"  Esfera: {row.get('OI_SPH', 'N/A')}, Cilindro: {row.get('OI_CYL', 'N/A')}, Eje: {row.get('OI_EJE', 'N/A')}")
                    
                    st.markdown("---")
        else:
            st.warning("No se encontraron pacientes con esos datos.")

def pantalla_recordatorios(df):
    st.header("🔔 Recordatorios de Citas")
    meses_sin_control = st.slider("Mostrar pacientes sin control en más de (meses):", 6, 36, 12)
    
    if not df.empty and 'Última_visita' in df.columns:
        fecha_limite = datetime.datetime.now() - datetime.timedelta(days=30.44 * meses_sin_control)
        
        sin_control = df[df['Última_visita'] < fecha_limite].sort_values('Última_visita')
        
        if not sin_control.empty:
            st.warning(f"⚠️ **{len(sin_control)}** pacientes con control pendiente.")
            st.write("Puedes llamarlos para ofrecerles una nueva cita.")
            
            # Crear una tabla con los datos clave
            df_mostrar = sin_control[['Nombre', 'Teléfono', 'Última_visita']].copy()
            df_mostrar['Última_visita'] = df_mostrar['Última_visita'].dt.strftime('%d/%m/%Y')
            
            st.dataframe(df_mostrar, use_container_width=True)
            
        else:
            st.info("✅ Todos los pacientes tienen su control al día (según el filtro seleccionado).")
    else:
        st.warning("No hay datos de fechas de visita para mostrar recordatorios.")

# --- EJECUCIÓN DE LA APP ---
if __name__ == "__main__":
    mostrar_header()
    df_pacientes = cargar_datos()

    menu = st.sidebar.radio("Menú", ["🔍 Buscar Paciente", "🔔 Recordatorios de Citas"])

    if menu == "🔍 Buscar Paciente":
        pantalla_buscar_paciente(df_pacientes)
    elif menu == "🔔 Recordatorios de Citas":
        pantalla_recordatorios(df_pacientes)
