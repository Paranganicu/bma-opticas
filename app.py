import pandas as pd
import streamlit as st
import datetime
from datetime import datetime as dt, timezone
import re
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from html import escape
import uuid
import os
import logging
import magic
from typing import Optional, Dict, Any

# === CONFIGURACIÓN INICIAL ===
logging.basicConfig(filename='app.log', level=logging.INFO, 
                   format='%(asctime)s - %(levelname)s - %(message)s')

# === CONSTANTES ===
COLUMNAS_OPTICAS = ['OD_SPH', 'OD_CYL', 'OD_EJE', 'OI_SPH', 'OI_CYL', 'OI_EJE', 'DP_Lejos', 'DP_CERCA', 'ADD']
MIME_VALIDOS = ['application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']

# === FUNCIONES DE VALIDACIÓN ===
def validar_rut_completo(rut: str) -> bool:
    """Valida el RUT chileno incluyendo dígito verificador"""
    try:
        rut = rut.upper().replace(".", "").replace("-", "")
        if not re.match(r'^[0-9]{7,8}[0-9K]$', rut):
            return False
            
        cuerpo, dv = rut[:-1], rut[-1]
        
        suma = 0
        multiplo = 2
        for c in reversed(cuerpo):
            suma += int(c) * multiplo
            multiplo = multiplo + 1 if multiplo < 7 else 2
        
        dv_esperado = str(11 - (suma % 11))
        dv_esperado = {
            '10': 'K',
            '11': '0'
        }.get(dv_esperado, dv_esperado)
        
        return dv == dv_esperado
    except Exception as e:
        logging.error(f"Error validando RUT {rut}: {str(e)}")
        return False

def enmascarar_rut(rut: str) -> str:
    """Enmascara parcialmente el RUT para protección de datos"""
    if not isinstance(rut, str):
        return ""
    
    partes = rut.split("-")
    if len(partes) != 2:
        return rut
    
    cuerpo = partes[0]
    if len(cuerpo) > 4:
        cuerpo = f"{cuerpo[:-4]}****"
    
    return f"{cuerpo}-{partes[1]}"

def es_excel_valido(file_path: str) -> bool:
    """Verifica que el archivo sea realmente un Excel válido"""
    try:
        mime = magic.from_file(file_path, mime=True)
        return mime in MIME_VALIDOS
    except Exception as e:
        logging.error(f"Error validando archivo Excel: {str(e)}")
        return False

# === FUNCIONES DE DATOS ===
@st.cache_data(hash_funcs={pd.DataFrame: lambda _: None}, ttl=3600)
def cargar_datos() -> pd.DataFrame:
    """Carga y valida los datos de pacientes"""
    try:
        if not os.path.exists("Pacientes.xlsx"):
            st.error("❌ Archivo 'Pacientes.xlsx' no encontrado")
            logging.error("Archivo Pacientes.xlsx no encontrado")
            return pd.DataFrame()
        
        if not es_excel_valido("Pacientes.xlsx"):
            st.error("❌ El archivo no es un Excel válido")
            logging.error("Archivo no es un Excel válido")
            return pd.DataFrame()
        
        df = pd.read_excel("Pacientes.xlsx", sheet_name="Sheet1")
        df.columns = df.columns.str.strip()
        
        # Validación de RUTs
        if 'Rut' in df.columns:
            df['Rut_Válido'] = df['Rut'].apply(validar_rut_completo)
            if not df['Rut_Válido'].all():
                rut_invalidos = df[~df['Rut_Válido']]['Rut'].tolist()
                st.warning(f"⚠️ {len(rut_invalidos)} RUTs no válidos detectados")
                logging.warning(f"RUTs inválidos: {rut_invalidos[:5]}...")
        
        # Conversión de tipos
        if 'Última_visita' in df.columns:
            df['Última_visita'] = pd.to_datetime(df['Última_visita'], errors='coerce')
            df['Última_visita'] = df['Última_visita'].dt.tz_localize(timezone.utc)
        
        if 'Valor' in df.columns:
            df['Valor'] = pd.to_numeric(df['Valor'], errors='coerce').fillna(0)
        
        # Limpieza de columnas ópticas
        for col in COLUMNAS_OPTICAS:
            if col in df.columns:
                df[col] = df[col].fillna('').apply(lambda x: str(x).strip())
        
        logging.info(f"Datos cargados correctamente. {len(df)} registros")
        return df
    
    except Exception as e:
        st.error(f"❌ Error crítico al cargar datos: {str(e)}")
        logging.critical(f"Error al cargar datos: {str(e)}", exc_info=True)
        return pd.DataFrame()

# === FUNCIONES DE PDF ===
def generar_pdf_receta(paciente: Dict[str, Any]) -> BytesIO:
    """Genera un PDF seguro con la receta óptica"""
    try:
        # Crear buffer seguro
        buffer = BytesIO()
        filename = f"temp_{uuid.uuid4()}.pdf"
        
        # Configuración segura del PDF
        c = canvas.Canvas(filename, pagesize=letter)
        c.setTitle(f"Receta Óptica - {escape(str(paciente.get('Nombre', 'Paciente sin nombre')))}")
        
        # Encabezado
        c.setFont("Helvetica-Bold", 16)
        c.drawString(100, 750, "BMA Ópticas - Receta Óptica")
        
        # Datos del paciente (sanitizados)
        c.setFont("Helvetica", 12)
        c.drawString(100, 730, f"Paciente: {escape(str(paciente.get('Nombre', '')))}")
        c.drawString(100, 710, f"RUT: {enmascarar_rut(paciente.get('Rut', ''))}")
        c.drawString(100, 690, f"Fecha: {dt.now(timezone.utc).strftime('%d/%m/%Y')}")
        
        # Datos ópticos
        y_pos = 650
        c.setFont("Helvetica-Bold", 14)
        c.drawString(100, y_pos, "Prescripción Óptica:")
        y_pos -= 30
        
        # Tabla de valores
        c.setFont("Helvetica-Bold", 12)
        c.drawString(100, y_pos, "Parámetro")
        c.drawString(200, y_pos, "Ojo Derecho (OD)")
        c.drawString(350, y_pos, "Ojo Izquierdo (OI)")
        y_pos -= 20
        
        c.setFont("Helvetica", 12)
        for param, od, oi in [("ESF", paciente.get('OD_SPH', ''), paciente.get('OI_SPH', '')),
                             ("CIL", paciente.get('OD_CYL', ''), paciente.get('OI_CYL', '')),
                             ("EJE", paciente.get('OD_EJE', ''), paciente.get('OI_EJE', ''))]:
            c.drawString(100, y_pos, param)
            c.drawString(200, y_pos, str(od))
            c.drawString(350, y_pos, str(oi))
            y_pos -= 20
        
        # Datos adicionales
        y_pos -= 20
        c.setFont("Helvetica-Bold", 12)
        c.drawString(100, y_pos, "Adicionales:")
        y_pos -= 20
        
        c.setFont("Helvetica", 12)
        c.drawString(120, y_pos, f"DP Lejos: {escape(str(paciente.get('DP_Lejos', '')))}")
        y_pos -= 20
        c.drawString(120, y_pos, f"DP Cerca: {escape(str(paciente.get('DP_CERCA', '')))}")
        y_pos -= 20
        c.drawString(120, y_pos, f"ADD: {escape(str(paciente.get('ADD', '')))}")
        
        # Firma segura
        c.setFont("Helvetica-Bold", 12)
        c.drawString(400, 100, "Firma del Óptico")
        c.line(400, 95, 500, 95)
        
        c.save()
        
        # Leer y limpiar archivo temporal
        with open(filename, "rb") as f:
            buffer.write(f.read())
        os.remove(filename)
        
        buffer.seek(0)
        logging.info(f"PDF generado para {paciente.get('Nombre')}")
        return buffer
    
    except Exception as e:
        logging.error(f"Error generando PDF: {str(e)}", exc_info=True)
        st.error("❌ Error al generar receta PDF")
        return BytesIO()

# === INTERFAZ DE USUARIO ===
def mostrar_header():
    """Muestra el encabezado de la aplicación"""
    try:
        st.image("logo.png", use_column_width=True)
    except FileNotFoundError:
        st.warning("⚠️ Logo no encontrado (logo.png)")
        logging.warning("Logo no encontrado")
    
    st.markdown("""
    <h2 style='text-align: center; color: #005f87;'>👓 Sistema de Gestión BMA Ópticas</h2>
    <h3 style='text-align: center; color: gray;'>Cuidamos tus ojos, cuidamos de ti.</h3>
    """, unsafe_allow_html=True)

def pantalla_inicio(df: pd.DataFrame):
    """Pantalla principal del sistema"""
    st.markdown("### 🏠 Bienvenido al Sistema BMA Ópticas")
    st.write("Sistema integral para gestión de pacientes, ventas y recetas ópticas.")
    
    if not df.empty:
        st.subheader("📊 Resumen General")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Pacientes", len(df))
        with col2:
            con_recetas = len(df[df['OD_SPH'].notna() | df['OI_SPH'].notna()])
            st.metric("Pacientes con Recetas", con_recetas)
        with col3:
            st.metric("Ventas Totales", f"${df['Valor'].sum():,.0f}")
        
        st.markdown("---")
        st.subheader("📂 Vista Previa de Datos")
        st.dataframe(df.head().style.format({
            'Valor': '${:,.0f}',
            'Última_visita': lambda x: x.strftime('%d/%m/%Y') if not pd.isna(x) else ''
        }))

def pantalla_pacientes(df: pd.DataFrame):
    """Gestión de pacientes con filtros avanzados"""
    st.subheader("👁️ Gestión de Pacientes")
    
    if df.empty:
        st.warning("⚠️ No hay datos para mostrar")
        return
    
    # Filtros avanzados
    with st.expander("🔍 Filtros Avanzados", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            busqueda = st.text_input("Buscar por nombre o RUT:")
        with col2:
            mostrar_rut_completo = st.checkbox("Mostrar RUT completo", False)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            tipos_lente = ["Todos"] + sorted(df['Tipo_Lente'].dropna().unique().tolist())
            filtro_tipo = st.selectbox("Tipo de lente:", tipos_lente)
        with col2:
            armazones = ["Todos"] + sorted(df['Armazon'].dropna().unique().tolist())
            filtro_armazon = st.selectbox("Armazón:", armazones)
        with col3:
            edad_min, edad_max = int(df['Edad'].min()), int(df['Edad'].max())
            rango_edad = st.slider("Rango de edad:", edad_min, edad_max, (edad_min, edad_max))
    
    # Aplicar filtros
    df_filtrado = df.copy()
    
    if busqueda:
        # Construimos una máscara OR entre las 3 columnas
        mask = (
        df_filtrado["Nombre"].str.contains(busqueda, case=False, na=False) |
        df_filtrado["Rut"].astype(str).str.contains(busqueda, case=False, na=False) |
        df_filtrado["Teléfono"].astype(str).str.contains(busqueda, case=False, na=False))

    df_filtrado = df_filtrado[mask]    
    if filtro_tipo != "Todos":
        df_filtrado = df_filtrado[df_filtrado['Tipo_Lente'] == filtro_tipo]
    
    if filtro_armazon != "Todos":
# ----------------- FILTRO DE EDAD ----------------- #
    if 'rango_edad' in locals():
        df_filtrado = df_filtrado[
        (df_filtrado['Edad'] >= rango_edad[0]) &
        (df_filtrado['Edad'] <= rango_edad[1])
    ]
# --------------- FIN FILTRO DE EDAD --------------- 
  
  #df_filtrado = df_filtrado[df_filtrado['Armazon'] == filtro_armazon]
    # Mostrar resultados
    st.write(f"📋 Mostrando {len(df_filtrado)} de {len(df)} pacientes")
    
    columnas = ['Nombre', 'Rut', 'Edad', 'Teléfono', 'Última_visita', 'Tipo_Lente', 'Armazon']
    if not df_filtrado.empty:
        df_mostrar = df_filtrado[columnas].copy()
        
        if not mostrar_rut_completo:
            df_mostrar['Rut'] = df_mostrar['Rut'].apply(enmascarar_rut)
        
        df_mostrar['Última_visita'] = df_mostrar['Última_visita'].dt.strftime('%d/%m/%Y')
        
        st.dataframe(
            df_mostrar.style.format({'Edad': '{:.0f}'}),
            use_container_width=True,
            height=min(400, 35 * (len(df_mostrar) + 1))
    else:
        st.warning("No se encontraron pacientes con los filtros aplicados")

    def pantalla_ventas(df: pd.DataFrame):
    """Análisis de ventas y finanzas"""
    st.subheader("💰 Gestión de Ventas")
    
    if df.empty:
        st.warning("⚠️ No hay datos de ventas")
        return
    
        df_ventas = df[df['Valor'].notna() & (df['Valor'] > 0)]
    if df_ventas.empty:
        st.warning("⚠️ No hay ventas válidas registradas")
        return
    
    # Métricas clave
    st.subheader("📈 Métricas Clave")
    col1, col2, col3 = st.columns(3)
    col1.metric("Ventas Totales", f"${df_ventas['Valor'].sum():,.0f}")
    col2.metric("Ticket Promedio", f"${df_ventas['Valor'].mean():,.0f}")
    col3.metric("N° de Transacciones", len(df_ventas))
    
    # Análisis por forma de pago
    st.markdown("---")
    st.subheader("💳 Ventas por Forma de Pago")
    
    if 'FORMA_PAGO' in df_ventas.columns:
        ventas_pago = df_ventas.groupby('FORMA_PAGO').agg(
            Total=('Valor', 'sum'),
            Cantidad=('Valor', 'count'),
            Promedio=('Valor', 'mean')
        ).sort_values('Total', ascending=False)
        
        st.bar_chart(ventas_pago['Total'])
        st.dataframe(
            ventas_pago.style.format({
                'Total': '${:,.0f}',
                'Promedio': '${:,.0f}'
            }),
            use_container_width=True)
    
    # Tendencia temporal
    st.markdown("---")
    st.subheader("📅 Evolución Temporal")
    
    if 'Última_visita' in df_ventas.columns:
        df_ventas['Mes'] = df_ventas['Última_visita'].dt.to_period('M')
        ventas_mensuales = df_ventas.groupby('Mes').agg(
            Total=('Valor', 'sum'),
            Pacientes=('Nombre', 'nunique')
        ).reset_index()
        
        ventas_mensuales['Mes'] = ventas_mensuales['Mes'].astype(str)
        ventas_mensuales.set_index('Mes', inplace=True)
        
        tab1, tab2 = st.tabs(["Ventas Totales", "Pacientes Atendidos"])
        
        with tab1:
            st.line_chart(ventas_mensuales['Total'])
        with tab2:
            st.bar_chart(ventas_mensuales['Pacientes'])

    def pantalla_reportes(df: pd.DataFrame):
        """Reportes analíticos y gestión de recetas"""
        st.subheader("📊 Reportes Analíticos")
    
    if df.empty:
        st.warning("⚠️ No hay datos para reportar")
        return
    
    # Filtro de fechas
        st.sidebar.subheader("Filtros de Reporte")
        fecha_min = df['Última_visita'].min().to_pydatetime()
        fecha_max = df['Última_visita'].max().to_pydatetime()
    
    rango_fechas = st.sidebar.date_input(
        "Rango de fechas:",
        [fecha_min, fecha_max],
        min_value=fecha_min,
        max_value=fecha_max)
    
    if len(rango_fechas) == 2:
        df_reportes = df[
            (df['Última_visita'].dt.date >= rango_fechas[0]) & 
            (df['Última_visita'].dt.date <= rango_fechas[1])]
    else:
        df_reportes = df.copy()
    
    # Ventas por tipo de lente
    st.subheader("👓 Ventas por Tipo de Lente")
    
    df_ventas = df_reportes[df_reportes['Valor'] > 0]
    if not df_ventas.empty:
        ventas_tipo = df_ventas.groupby('Tipo_Lente').agg(
            Total=('Valor', 'sum'),
            Cantidad=('Valor', 'count'),
            Promedio=('Valor', 'mean')
        ).sort_values('Total', ascending=False)
        
        col1, col2 = st.columns([1, 2])
        with col1:
            st.dataframe(
                ventas_tipo.style.format({
                    'Total': '${:,.0f}',
                    'Promedio': '${:,.0f}'
                }),
                height=400)
    with col2:
        st.bar_chart(ventas_tipo['Total'])
    else:
        st.warning("No hay ventas en el período seleccionado")
    
    # Gestión de recetas
    st.markdown("---")
    st.subheader("📝 Recetas Ópticas")
    
    has_optica_data = df_reportes[COLUMNAS_OPTICAS[:6]].notna().any(axis=1)
    df_recetas = df_reportes[has_optica_data]
    
    if df_recetas.empty:
        st.info("ℹ️ No hay recetas registradas en el período")
        return
    
    # Búsqueda de recetas
        busqueda = st.text_input("Buscar receta por nombre o RUT:")
    if busqueda:
        df_recetas = df_recetas[
        df_recetas['Nombre'].str.contains(busqueda, case=False, na=False) |
        df_recetas['Rut'].str.contains(busqueda, case=False, na=False)]
    
    # Mostrar recetas
    for _, paciente in df_recetas.iterrows():
        with st.expander(f"👤 {paciente['Nombre']} - {enmascarar_rut(paciente['Rut'])}", expanded=False):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Ojo Derecho (OD)**")
                st.text(f"ESF: {paciente.get('OD_SPH', '')}")
                st.text(f"CIL: {paciente.get('OD_CYL', '')}")
                st.text(f"EJE: {paciente.get('OD_EJE', '')}")
            
            with col2:
                st.markdown("**Ojo Izquierdo (OI)**")
                st.text(f"ESF: {paciente.get('OI_SPH', '')}")
                st.text(f"CIL: {paciente.get('OI_CYL', '')}")
                st.text(f"EJE: {paciente.get('OI_EJE', '')}")
            
            st.markdown("**Adicionales**")
            cols = st.columns(3)
            with cols[0]:
                st.text(f"DP Lejos: {paciente.get('DP_Lejos', '')}")
            with cols[1]:
                st.text(f"DP Cerca: {paciente.get('DP_CERCA', '')}")
            with cols[2]:
                st.text(f"ADD: {paciente.get('ADD', '')}")
            
            st.text(f"Fecha: {paciente['Última_visita'].strftime('%d/%m/%Y')}")
            
            # Generar PDF
            if st.button(f"📄 Generar PDF", key=f"pdf_{paciente['Rut']}"):
                with st.spinner("Generando receta..."):
                    pdf = generar_pdf_receta(paciente)
                    st.download_button(
                        label="⬇️ Descargar Receta",
                        data=pdf,
                        file_name=f"Receta_{paciente['Nombre'].replace(' ', '_')}.pdf",
                        mime="application/pdf")

def pantalla_alertas(df: pd.DataFrame):
    """Sistema de alertas y recordatorios"""
    st.subheader("⚠️ Alertas del Sistema")
    
    if df.empty:
        st.warning("⚠️ No hay datos para generar alertas")
        return
    
    # Pacientes sin control reciente
    st.markdown("### 📅 Pacientes sin Control Reciente")
    fecha_limite = dt.now(timezone.utc) - datetime.timedelta(days=365)
    
    sin_control = df[df['Última_visita'] < fecha_limite]
    if not sin_control.empty:
        st.warning(f"🔴 {len(sin_control)} pacientes sin control en más de 1 año")
        
        cols = st.columns(3)
        cols[0].metric("Total", len(sin_control))
        cols[1].metric("Mayor antigüedad", 
                      sin_control['Última_visita'].min().strftime('%d/%m/%Y'))
        cols[2].metric("Ventas potenciales", 
                      f"${sin_control['Valor'].mean():,.0f} promedio")
        
        with st.expander("📋 Ver detalles", expanded=False):
            st.dataframe(
                sin_control[['Nombre', 'Rut', 'Teléfono', 'Última_visita', 'Tipo_Lente']]
                .sort_values('Última_visita')
                .assign(Última_visita=lambda x: x['Última_visita'].dt.strftime('%d/%m/%Y'))
                .style.applymap(lambda x: 'color: red', subset=['Última_visita']))
            
            # Exportar lista
            csv = sin_control[['Nombre', 'Rut', 'Teléfono', 'Última_visita']].to_csv(index=False)
            st.download_button(
                "📤 Exportar lista para contacto",
                data=csv,
                file_name="pacientes_sin_control.csv",
                mime="text/csv")
    else:
        st.success("✅ Todos los pacientes tienen controles recientes")
    
    # Ventas destacadas
    st.markdown("---")
    st.subheader("💰 Ventas Destacadas")
    
    if 'Valor' in df.columns and len(df[df['Valor'] > 0]) > 10:
        limite_superior = df['Valor'].quantile(0.95)
        ventas_destacadas = df[df['Valor'] > limite_superior]
        
        if not ventas_destacadas.empty:
            st.info(f"⭐ {len(ventas_destacadas)} ventas superiores a ${limite_superior:,.0f} (percentil 95)")
            
            cols = st.columns(4)
            cols[0].metric("Valor mínimo", f"${ventas_destacadas['Valor'].min():,.0f}")
            cols[1].metric("Valor máximo", f"${ventas_destacadas['Valor'].max():,.0f}")
            cols[2].metric("Promedio", f"${ventas_destacadas['Valor'].mean():,.0f}")
            cols[3].metric("Total", f"${ventas_destacadas['Valor'].sum():,.0f}")
            
            with st.expander("📋 Ver ventas destacadas", expanded=False):
                st.dataframe(
                    ventas_destacadas[['Nombre', 'Valor', 'Tipo_Lente', 'FORMA_PAGO', 'Última_visita']]
                    .sort_values('Valor', ascending=False)
                    .assign(Última_visita=lambda x: x['Última_visita'].dt.strftime('%d/%m/%Y')))
        else:
            st.info("ℹ️ No hay ventas destacadas en el percentil 95")

# === EJECUCIÓN PRINCIPAL ===
def main():
    # Configuración de página
    mostrar_header()
    
    # Cargar datos
    with st.spinner("Cargando datos..."):
        df = cargar_datos()
    
    # Menú principal
    menu = st.sidebar.radio(
        "Navegación",
        ["🏠 Inicio", "👁️ Pacientes", "💰 Ventas", "📊 Reportes", "⚠️ Alertas"],
        index=0)
    
    # Mostrar pantalla seleccionada
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
    
    # Footer
    st.sidebar.markdown("---")
    st.sidebar.markdown("**BMA Ópticas** v2.0")
    st.sidebar.markdown(f"Última actualización: {dt.now(timezone.utc).strftime('%d/%m/%Y %H:%M')}")
    st.sidebar.markdown("Sistema seguro - © 2023")

if __name__ == "__main__":
    main()
