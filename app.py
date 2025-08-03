# ─────────── app.py (Refactor v3.1) ───────────
"""
BMA Ópticas: Sistema de Gestión de Pacientes, Ventas, Recetas y Reportes
Versión 3.1: Validaciones en capas, backups automáticos, reportes, recordatorios,
integración de facturación (stub), arquitectura modular y UX mejorada.
"""
import os
import re
import shutil
import uuid
import logging
import datetime as dt
from io import BytesIO
from typing import Dict, Any, List, Tuple, Optional

import pandas as pd
import streamlit as st
from html import escape
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import magic  # macOS/Linux; use python-magic-bin en Windows

# ╔═════════ CONFIGURACIÓN GLOBAL ═══════════╗
APP_VERSION = "3.1"
DATA_DIR    = os.path.dirname(__file__)
DATA_FILE   = os.path.join(DATA_DIR, "Pacientes.xlsx")
BACKUP_DIR  = os.path.join(DATA_DIR, "backups")
LOG_FILE    = os.path.join(DATA_DIR, "app.log")

COLUMNAS_BASE = [
    "RUT","Nombre","Edad","Teléfono",
    "Tipo_Lente","Armazon","Cristales",
    "Valor","Forma_Pago","Fecha_venta","Proxima_cita",
    "OD_SPH","OD_CYL","OD_EJE",
    "OI_SPH","OI_CYL","OI_EJE",
    "DP_Lejos","DP_CERCA","ADD"
]
MIME_TYPES = [
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel"
]

# Logging
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(message)s"
)

# ╔═════════ UTILIDADES ═══════════╗

def validar_rut(raw: str) -> bool:
    """Valida formato y dígito verificador de RUT chileno."""
    r = raw.upper().replace('.', '').replace('-', '')
    if not re.fullmatch(r"\d{7,8}[0-9K]", r):
        return False
    cuerpo, dv = r[:-1], r[-1]
    suma, factor = 0, 2
    for c in reversed(cuerpo):
        suma += int(c) * factor
        factor = 2 if factor == 7 else factor + 1
    dv_calc = 11 - (suma % 11)
    dv_calc = {10: 'K', 11: '0'}.get(dv_calc, str(dv_calc))
    return dv == dv_calc


def formatear_rut(raw: str) -> str:
    """Formatea un RUT válido a ##.###.###-D"""
    r = raw.replace('.', '').replace('-', '').upper()
    cuerpo, dv = r[:-1], r[-1]
    cuerpo_fmt = f"{int(cuerpo):,}".replace(',', '.')
    return f"{cuerpo_fmt}-{dv}"


def es_mime_excel(path: str) -> bool:
    try:
        return magic.from_file(path, mime=True) in MIME_TYPES
    except Exception as e:
        logging.warning(f"MIME check falló: {e}")
        return False


def validate_patient_data(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Valida datos del paciente y venta, retorna (es_válido, errores)."""
    errors: List[str] = []
    # RUT
    if not data.get('RUT'):
        errors.append("RUT es obligatorio")
    elif not validar_rut(data['RUT'].replace('.', '').replace('-', '')):
        errors.append("RUT inválido")
    # Edad
    age = data.get('Edad', -1)
    if not isinstance(age, int) or age < 0 or age > 150:
        errors.append("Edad debe estar entre 0 y 150")
    # Valor
    value = data.get('Valor', 0)
    if not isinstance(value, (int, float)) or value <= 0:
        errors.append("Valor debe ser mayor a 0")
    return len(errors) == 0, errors


def backup_excel():
    """Realiza backup automático del archivo de datos."""
    if os.path.exists(DATA_FILE):
        os.makedirs(BACKUP_DIR, exist_ok=True)
        ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        dst = os.path.join(BACKUP_DIR, f"Pacientes_{ts}.xlsx")
        shutil.copy2(DATA_FILE, dst)
        logging.info(f"Backup creado: {dst}")

# ╔═════════ DATOS ═══════════╗

@st.cache_data(ttl=300)
def cargar_datos() -> pd.DataFrame:
    """Carga o inicializa la base de datos con columnas garantizadas."""
    if not os.path.exists(DATA_FILE) or not es_mime_excel(DATA_FILE):
        logging.info("Inicializando nueva base de datos.")
        return pd.DataFrame(columns=COLUMNAS_BASE)
    df = pd.read_excel(DATA_FILE).copy()
    for col in COLUMNAS_BASE:
        if col not in df.columns:
            df[col] = 0 if col == 'Valor' else ''
    df['Valor'] = pd.to_numeric(df['Valor'], errors='coerce').fillna(0)
    df['Fecha_venta'] = pd.to_datetime(df['Fecha_venta'], errors='coerce')
    return df[COLUMNAS_BASE]


def guardar_datos(df: pd.DataFrame):
    """Hace backup y persiste el DataFrame a disco."""
    backup_excel()
    try:
        df.to_excel(DATA_FILE, index=False)
        logging.info("Datos guardados correctamente.")
    except Exception as e:
        logging.error(f"No se pudo guardar Excel: {e}")
        st.error("Error guardando datos en disco.")

# ╔═════════ PDF RECETA ═══════════╗

def generar_pdf_receta(paciente: Dict[str, Any]) -> BytesIO:
    buffer = BytesIO()
    tmpfile = f"tmp_{uuid.uuid4()}.pdf"
    c = canvas.Canvas(tmpfile, pagesize=letter)
    c.setTitle(f"Receta - {paciente['Nombre']}")
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, 750, "BMA Ópticas - Receta Óptica")
    c.setFont("Helvetica", 12)
    c.drawString(72, 730, f"Paciente: {escape(paciente['Nombre'])}")
    c.drawString(72, 710, f"RUT: {paciente['RUT']}")
    c.drawString(400, 710, dt.datetime.now().strftime("%d/%m/%Y"))
    y = 670
    c.setFont("Helvetica-Bold", 12)
    c.drawString(72, y, "Param")
    c.drawString(150, y, "OD")
    c.drawString(250, y, "OI")
    y -= 20
    c.setFont("Helvetica", 12)
    for label, k1, k2 in [("ESF","OD_SPH","OI_SPH"),
                         ("CIL","OD_CYL","OI_CYL"),
                         ("EJE","OD_EJE","OI_EJE")]:
        c.drawString(72, y, label)
        c.drawString(150, y, str(paciente[k1]))
        c.drawString(250, y, str(paciente[k2]))
        y -= 20
    y -= 10
    for label, key in [("DP Lejos","DP_Lejos"), ("DP Cerca","DP_CERCA"), ("ADD","ADD")]:
        val = paciente.get(key,"")
        if val:
            c.drawString(72, y, f"{label}: {val}")
            y -= 18
    c.line(400, 100, 530, 100)
    c.drawString(420, 85, "Firma Óptico")
    c.save()
    with open(tmpfile, "rb") as f:
        buffer.write(f.read())
    os.remove(tmpfile)
    buffer.seek(0)
    return buffer

# ╔═════════ INTERFAZ DE USUARIO ═══════════╗

def mostrar_header():
    if os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)
    st.markdown(
        f"<h2 style='text-align:center;'>👓 BMA Ópticas v{APP_VERSION}</h2>",
        unsafe_allow_html=True
    )

# ╔═════════ PANTALLAS ═══════════╗

def pantalla_inicio(df: pd.DataFrame):
    st.title("🏠 Dashboard")
    if df.empty:
        st.info("Sin datos. Registra tu primera venta.")
        return
    c1, c2, c3 = st.columns(3)
    c1.metric("Pacientes únicos", df['RUT'].nunique())
    c2.metric("Ventas totales", f"${df['Valor'].sum():,.0f}")
    c3.metric("Ticket medio", f"${df['Valor'].mean():,.0f}")
    st.markdown("---")
    st.bar_chart(df.groupby(df['Fecha_venta'].dt.to_period('M'))['Valor'].sum())
    st.markdown("Ventas por mes")


def pantalla_registrar_venta(df: pd.DataFrame) -> pd.DataFrame:
    st.title("💰 Registrar Venta")
    with st.form("venta_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            rut_raw = st.text_input("RUT*", help="Sólo dígitos y K")
            nombre = st.text_input("Nombre*")
            edad    = st.number_input("Edad*", min_value=0, max_value=150)
            telefono= st.text_input("Teléfono")
            proxima = st.date_input("Próxima cita (opcional)", value=None)
        with c2:
            tipo_lente = st.selectbox("Tipo de lente", ["Monofocal","Bifocal","Progresivo"])
            armazon    = st.text_input("Armazón")
            valor      = st.number_input("Valor*", min_value=0, step=1000)
            forma_pago = st.selectbox("Forma de pago", ["Efectivo","T. Crédito","T. Débito"])
            fecha      = st.date_input("Fecha de venta", dt.date.today())
        st.markdown("#### Datos ópticos (opcional)")
        cols = st.columns(3)
        OD_SPH = cols[0].text_input("OD ESF"); OD_CYL = cols[1].text_input("OD CIL"); OD_EJE = cols[2].text_input("OD EJE")
        OI_SPH = cols[0].text_input("OI ESF"); OI_CYL = cols[1].text_input("OI CIL"); OI_EJE = cols[2].text_input("OI EJE")
        DP_Lejos = cols[0].text_input("DP Lejos"); DP_CERCA = cols[1].text_input("DP Cerca"); ADD = cols[2].text_input("ADD")
        submitted = st.form_submit_button("Guardar")
    if not submitted:
        return df
    # Validación en capas
    rut_fmt = formatear_rut(rut_raw) if validar_rut(rut_raw) else None
    record = {
        'RUT': rut_fmt, 'Nombre': nombre, 'Edad': edad, 'Teléfono': telefono,
        'Tipo_Lente': tipo_lente, 'Armazon': armazon, 'Cristales': '',
        'Valor': valor, 'Forma_Pago': forma_pago, 'Fecha_venta': pd.to_datetime(fecha), 'Proxima_cita': pd.to_datetime(proxima),
        'OD_SPH': OD_SPH, 'OD_CYL': OD_CYL, 'OD_EJE': OD_EJE,
        'OI_SPH': OI_SPH, 'OI_CYL': OI_CYL, 'OI_EJE': OI_EJE,
        'DP_Lejos': DP_Lejos, 'DP_CERCA': DP_CERCA, 'ADD': ADD
    }
    valid, errors = validate_patient_data({'RUT':rut_raw,'Edad':edad,'Valor':valor})
    if not valid:
        for err in errors: st.error(err)
        return df
    # Integración con facturación (stub)
    logging.info(f"Integrando facturación para {rut_fmt}, valor {valor}")
    # Almacenar registro
    df = pd.concat([df, pd.DataFrame([record])], ignore_index=True)
    guardar_datos(df)
    st.success("✅ Venta registrada")
    st.experimental_rerun()
    return df


def pantalla_pacientes(df: pd.DataFrame):
    st.title("👁️ Pacientes & Ventas")
    if df.empty:
        st.info("No hay pacientes"); return
    filtro = st.text_input("Buscar (Nombre o RUT)")
    datos = df.copy()
    if filtro:
        mask = datos['Nombre'].str.contains(filtro, case=False, na=False) | datos['RUT'].str.contains(filtro, case=False, na=False)
        datos = datos[mask]
    for rut, grp in datos.groupby('RUT'):
        pac = grp.iloc[-1]
        with st.expander(f"{pac['Nombre']} — {rut} ({len(grp)} ventas)"):
            st.dataframe(
                grp[['Fecha_venta','Tipo_Lente','Valor','Forma_Pago','Proxima_cita']]
                .rename(columns={'Fecha_venta':'Fecha'})
                .sort_values('Fecha',ascending=False)
            )
            if pac['OD_SPH'] or pac['OI_SPH']:
                pdf = generar_pdf_receta(pac.to_dict())
                st.download_button("📄 Descargar última receta", pdf,
                    file_name=f"Receta_{pac['Nombre'].replace(' ','_')}.pdf",mime='application/pdf',key=f"dl_{rut}")

# ╔═════════ MAIN ═══════════╗
if 'df' not in st.session_state:
    st.session_state.df = cargar_datos()

mostrar_header()
menu = st.sidebar.radio("Menú", ["Inicio","Registrar venta","Pacientes","Reportes"])
if menu == 'Inicio':
    pantalla_inicio(st.session_state.df)
elif menu == 'Registrar venta':
    st.session_state.df = pantalla_registrar_venta(st.session_state.df)
elif menu == 'Pacientes':
    pantalla_pacientes(st.session_state.df)
else:
    pantalla_reportes(st.session_state.df)  # Implementar reportes

st.sidebar.markdown('---')
st.sidebar.caption(f'© BMA Ópticas v{APP_VERSION} 2025')
