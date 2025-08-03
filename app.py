"""BMA Ópticas – versión unificada
---------------------------------
• Punto único de ingreso = módulo **Ventas** (formulario completo)
• Validaciones y normalización (RUT, nombre, valor numérico…)
• `st.rerun()` en lugar de API experimental
"""

import os, re, uuid, logging, datetime as dt
from io import BytesIO
from typing import Dict, Any, Optional

import pandas as pd
import streamlit as st
from html import escape
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import magic                             # validar MIME en Streamlit Cloud

# ╔════════════ CONFIG GLOBAL ════════════╗
st.set_page_config("BMA Ópticas", "👓", layout="wide")
logging.basicConfig(filename="app.log", level=logging.INFO,
                    format="%(asctime)s – %(levelname)s – %(message)s")

COLUM_OPT = [
    "OD_SPH","OD_CYL","OD_EJE","OI_SPH","OI_CYL","OI_EJE",
    "DP_Lejos","DP_CERCA","ADD"
]
MIME_XLSX = {
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
ARCHIVO_XLSX = "Pacientes.xlsx"

# ╔════════════ UTILIDADES ════════════╗
RUT_RE = re.compile(r"^([0-9]{1,3}(?:\.[0-9]{3})*)\-([0-9Kk])$")


def validar_rut(rut: str) -> bool:
    """Valida RUT chileno con formato 12.345.678-5 o 12345678-5"""
    rut = rut.upper().strip()
    m = RUT_RE.match(rut)
    if not m:
        return False
    cuerpo = m.group(1).replace(".", "")
    dv_ing = m.group(2)
    suma, fac = 0, 2
    for d in reversed(cuerpo):
        suma += int(d) * fac
        fac = 2 if fac == 7 else fac + 1
    dv_calc = 11 - (suma % 11)
    dv_calc = {10: "K", 11: "0"}.get(dv_calc, str(dv_calc))
    return dv_ing == dv_calc


def normalizar_rut(rut: str) -> str:
    """Devuelve el RUT formateado con puntos y guion (XX.XXX.XXX‐DV)"""
    rut = rut.upper().replace(".", "").replace("-", "")
    cuerpo, dv = rut[:-1], rut[-1]
    cuerpo = f"{int(cuerpo):,}".replace(",", ".")  # agrega puntos
    return f"{cuerpo}-{dv}"


def enmascarar_rut(rut: str) -> str:
    if "-" not in rut:
        return rut
    cuerpo, dv = rut.split("-")
    cuerpo = cuerpo[:-4] + "****" if len(cuerpo) > 4 else cuerpo
    return f"{cuerpo}-{dv}"


def excel_valido(path: str) -> bool:
    try:
        return magic.from_file(path, mime=True) in MIME_XLSX
    except Exception as e:
        logging.error(f"MIME error: {e}")
        return False


# ╔════════════ DATA ════════════╗
@st.cache_data(ttl=3600, hash_funcs={pd.DataFrame: lambda _: None})
def cargar_datos() -> pd.DataFrame:
    if not os.path.exists(ARCHIVO_XLSX):
        return pd.DataFrame()
    if not excel_valido(ARCHIVO_XLSX):
        st.error("Archivo XLSX inválido")
        return pd.DataFrame()
    df = pd.read_excel(ARCHIVO_XLSX)
    df.columns = df.columns.str.strip()
    # normalizaciones
    if "Rut" in df:
        df["Rut"] = df["Rut"].astype(str).apply(normalizar_rut)
        df["Rut_V"] = df["Rut"].apply(validar_rut)
    if "Nombre" in df:
        df["Nombre"] = df["Nombre"].str.title().str.strip()
    if "Valor" in df:
        df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce").fillna(0)
    if "Última_visita" in df:
        df["Última_visita"] = pd.to_datetime(df["Última_visita"], errors="coerce")
    for c in COLUM_OPT:
        if c in df:
            df[c] = df[c].fillna("").astype(str)
    return df


def guardar_datos(df: pd.DataFrame):
    try:
        df.to_excel(ARCHIVO_XLSX, index=False)
        logging.info("Base actualizada")
    except Exception as e:
        st.warning(f"No se pudo guardar: {e}")


# ╔════════════ PDF ════════════╗

def pdf_receta(p: Dict[str, Any]) -> BytesIO:
    tmp = f"tmp_{uuid.uuid4()}.pdf"
    buf = BytesIO()
    try:
        c = canvas.Canvas(tmp, pagesize=letter)
        c.setTitle(f"Receta – {p.get('Nombre','')}")
        c.setFont("Helvetica-Bold", 14); c.drawString(72, 750, "BMA Ópticas – Receta Óptica")
        c.setFont("Helvetica", 11)
        c.drawString(72, 730, f"Paciente: {escape(p.get('Nombre',''))}")
        c.drawString(72, 712, f"RUT: {enmascarar_rut(p.get('Rut',''))}")
        c.drawString(400, 712, dt.datetime.now().strftime("%d/%m/%Y"))
        y = 680
        c.setFont("Helvetica-Bold", 11); c.drawString(72, y, "Parámetro     OD        OI"); y -= 18
        for lab in [("ESF", "OD_SPH", "OI_SPH"), ("CIL", "OD_CYL", "OI_CYL"), ("EJE", "OD_EJE", "OI_EJE")]:
            c.drawString(72, y, f"{lab[0]:<9}{p.get(lab[1],''):<10}{p.get(lab[2],'')}"); y-=16
        y -= 12
        for extra in ["DP_Lejos","DP_CERCA","ADD"]:
            if p.get(extra):
                c.drawString(72, y, f"{extra}: {p[extra]}"); y -= 16
        c.line(400, 100, 520, 100); c.drawString(430, 85, "Firma Óptico")
        c.save(); buf.write(open(tmp, "rb").read())
    finally:
        if os.path.exists(tmp): os.remove(tmp)
    buf.seek(0); return buf


# ╔════════════ UI COMPONENTES ════════════╗

def encabezado():
    st.image("logo.png", use_container_width=True)
    st.markdown("<h2 style='text-align:center'>👓 Sistema de Gestión BMA Ópticas</h2>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align:center;color:gray'>Cuidamos tus ojos, cuidamos de ti</h4>", unsafe_allow_html=True)


# ╔════════════ MÓDULO VENTAS (Ingreso + dashboard) ════════════╗

def modulo_ventas(df: pd.DataFrame):
    st.header("💰 Registro de Venta + Receta")

    with st.form("form_venta", clear_on_submit=True):
        # ── secciones
        st.subheader("Datos del paciente ✍🏻")
        col1, col2, col3 = st.columns(3)
        with col1:
            rut_in = st.text_input("RUT* (con guion)")
        with col2:
            nombre_in = st.text_input("Nombre completo*")
        with col3:
            edad_in = st.number_input("Edad*", 0, 120, step=1, format="%d")
        tel_in = st.text_input("Teléfono / Celular")

        st.subheader("Venta 🛒")
        c1, c2, c3 = st.columns(3)
        with c1:
            tipo_lente = st.selectbox("Tipo de lente", ["Monofocal", "Bifocal", "Progresivo"])
        with c2:
            armazon = st.text_input("Armazón")
        with c3:
            valor = st.number_input("Valor venta $", 0, step=1000, format="%d")
        forma = st.selectbox("Forma de pago", ["Efectivo", "Tarjeta", "Transferencia"])
        fecha_venta = st.date_input("Fecha", dt.date.today())

        st.subheader("Receta 👓 (opcional)")
        r1, r2, r3 = st.columns(3)
        with r1:
            od_sph = st.text_input("OD ESF")
            oi_sph = st.text_input("OI ESF")
        with r2:
            od_cyl = st.text_input("OD CIL")
            oi_cyl = st.text_input("OI CIL")
        with r3:
            od_eje = st.text_input("OD EJE")
            oi_eje = st.text_input("OI EJE")
        c_dp1, c_dp2, c_add = st.columns(3)
        with c_dp1:
            dp_lejos = st.text_input("DP Lejos")
        with c_dp2:
            dp_cerca = st.text_input("DP Cerca")
        with c_add:
            add = st.text_input("ADD")

        enviar = st.form_submit_button("💾 Guardar venta")

    # ── procesamiento
    if enviar:
        if not (rut_in and nombre_in and validar_rut(rut_in)):
            st.error("RUT en formato 12.345.678-9 y nombre obligatorios")
            st.stop()

        rut_norm = normalizar_rut(rut_in)
        nombre_norm = nombre_in.title().strip()

        # Si paciente existe → actualizamos datos básicos
        if (df["Rut"] == rut_norm).any():
            idx = df[df["Rut"] == rut_norm].index[0]
            df.loc[idx, ["Nombre", "Edad", "Teléfono"]] = [nombre_norm, edad_in, tel_in]
        else:
            nueva_fila = {
                "Nombre": nombre_norm, "Rut": rut_norm, "Edad": edad_in,
                "Teléfono": tel_in, "Tipo_Lente": tipo_lente, "Armazon": armazon,
                "Valor": valor, "FORMA_PAGO": forma,
                "Última_visita": pd.to_datetime(fecha_venta),
                "OD_SPH": od_sph, "OD_CYL": od_cyl, "OD_EJE": od_eje,
                "OI_SPH": oi_sph, "OI_CYL": oi_cyl, "OI_EJE": oi_eje,
                "DP_Lejos": dp_lejos, "DP_CERCA": dp_cerca, "ADD": add
            }
            df = pd.concat([df, pd.DataFrame([
