# ───────────────────────────── app.py ─────────────────────────────
import os, re, uuid, logging, datetime as dt
from io import BytesIO
from typing import Dict, Any

import pandas as pd
import streamlit as st
from html import escape
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import magic  # ok en Streamlit Cloud

# ╔════════════ CONFIG GLOBAL ════════════╗
st.set_page_config(page_title="BMA Ópticas", page_icon="👓", layout="wide")
logging.basicConfig(filename="app.log", level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")

EXCEL_FILE      = "Pacientes.xlsx"
COLUMNAS_OPT    = ["OD_SPH","OD_CYL","OD_EJE","OI_SPH","OI_CYL","OI_EJE",
                   "DP_Lejos","DP_CERCA","ADD"]
MIME_VALIDOS    = ["application/vnd.ms-excel",
                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]

# ╔════════════ UTILIDADES ════════════╗
def limpiar_rut(raw: str) -> str:
    """Quita puntos y guion, devuelve cuerpo+DV en mayúsculas."""
    return re.sub(r"[^0-9Kk]", "", raw).upper()

def formatear_rut(raw: str) -> str:
    """Convierte 123456785 → 12.345.678-5 (sin validar)."""
    cuerpo, dv = raw[:-1], raw[-1]
    cuerpo = f"{int(cuerpo):,}".replace(",", ".")
    return f"{cuerpo}-{dv}"

def validar_rut(raw: str) -> bool:
    s = limpiar_rut(raw)
    if not re.fullmatch(r"[0-9]{7,8}[0-9K]", s): return False
    cuerpo, dv = s[:-1], s[-1]
    suma, fac = 0, 2
    for c in reversed(cuerpo):
        suma += int(c) * fac
        fac = 2 if fac == 7 else fac + 1
    resto = 11 - (suma % 11)
    dv_calc = {10:"K", 11:"0"}.get(resto, str(resto))
    return dv == dv_calc

def es_excel_valido(path:str)->bool:
    try:  return magic.from_file(path, mime=True) in MIME_VALIDOS
    except Exception as e:
        logging.error(f"MIME: {e}"); return False

# ╔════════════ CARGA / GUARDADO ════════════╗
@st.cache_data(ttl=3600, hash_funcs={pd.DataFrame:lambda _:None})
def cargar_datos() -> pd.DataFrame:
    if not os.path.exists(EXCEL_FILE):             # primera vez
        return pd.DataFrame()
    if not es_excel_valido(EXCEL_FILE):
        st.error("❌ El archivo existente no es un Excel válido"); return pd.DataFrame()
    try:
        df = pd.read_excel(EXCEL_FILE).copy()
        if "Última_visita" in df.columns:
            df["Última_visita"] = pd.to_datetime(df["Última_visita"], errors="coerce")
        if "Valor" in df.columns:
            df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce").fillna(0)
        return df
    except Exception as e:
        st.error(f"❌ Error leyendo Excel: {e}"); logging.critical(e, exc_info=True)
        return pd.DataFrame()

def guardar_df(df: pd.DataFrame):
    try:
        df.to_excel(EXCEL_FILE, index=False)
    except Exception as e:
        st.warning(f"No pude guardar el Excel: {e}")

# ╔════════════ PDF ════════════╗
def pdf_receta(p: Dict[str,Any]) -> BytesIO:
    tmp, buf = f"tmp_{uuid.uuid4()}.pdf", BytesIO()
    try:
        c = canvas.Canvas(tmp, pagesize=letter)
        c.setTitle(f"Receta {p['Nombre']}")
        c.setFont("Helvetica-Bold", 16); c.drawString(72,750,"BMA Ópticas – Receta")
        c.setFont("Helvetica",12)
        c.drawString(72,730,f"Paciente: {escape(p['Nombre'])}")
        c.drawString(72,712,f"RUT: {escape(p['RUT'])}")
        c.drawString(400,712,dt.datetime.now().strftime("%d/%m/%Y"))
        y = 680
        c.setFont("Helvetica-Bold",12); c.drawString(72,y,"OD / OI   ESF   CIL   EJE"); y -= 20
        c.setFont("Helvetica",12)
        c.drawString(72,y,f"OD: {p['OD_SPH']}  {p['OD_CYL']}  {p['OD_EJE']}"); y-=20
        c.drawString(72,y,f"OI: {p['OI_SPH']}  {p['OI_CYL']}  {p['OI_EJE']}"); y-=30
        for lab in ["DP_Lejos","DP_CERCA","ADD"]:
            if p.get(lab): c.drawString(72,y,f"{lab}: {p[lab]}"); y -= 18
        c.line(400,100,520,100); c.drawString(430,85,"Firma Óptico"); c.save()
        buf.write(open(tmp,"rb").read())
    except Exception as e: logging.error(e, exc_info=True)
    finally:                os.remove(tmp) if os.path.exists(tmp) else None
    buf.seek(0); return buf

# ╔════════════ UI – HEADER ════════════╗
def header():
    # versión compatible (<1.30)
    st.image("logo.png", use_column_width=True)
    st.markdown("<h2 style='text-align:center;'>👓 Sistema de Gestión BMA Ópticas</h2>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align:center;color:gray;'>Cuidamos tus ojos, cuidamos de ti</h4>", unsafe_allow_html=True)

# ╔════════════ PANTALLAS ════════════╗
def pantalla_inicio(df):
    st.header("🏠 Inicio")
    st.write("Bienvenido. Use el menú de la izquierda para comenzar.")
    if not df.empty:
        c1,c2,c3 = st.columns(3)
        c1.metric("Pacientes", len(df))
        c2.metric("Con receta", df[COLUMNAS_OPT[0]].notna().sum())
        c3.metric("Ventas 💲", f"${df['Valor'].sum():,.0f}")

def pantalla_registrar(df):
    st.header("💰 Registrar venta")
    with st.form("form_venta", clear_on_submit=True):
        c1,c2 = st.columns(2)
        # ▶ Entrada de datos
        rut_raw = c1.text_input("RUT* (solo números y K)")
        tipo_lente  = c2.selectbox("Tipo de lente", ["Monofocal","Bifocal","Progresivo"])
        nombre_raw  = c1.text_input("Nombre*")
        armazon     = c2.text_input("Armazón")
        edad_raw    = c1.text_input("Edad*")               # sin botones +/- 
        cristales   = c2.text_input("Cristales")
        telefono    = c1.text_input("Teléfono")
        valor_raw   = c2.text_input("Valor venta*", placeholder="Ej: 75000")
        forma_pago  = c2.selectbox("Forma de pago", ["Efectivo","T. Crédito","Débito"])
        fecha       = c2.date_input("Fecha de venta", dt.date.today())

        st.markdown("#### Datos ópticos (opcional)")
        od_esf, oi_esf, dp_lejos = st.columns(3)
        od_cil, oi_cil, dp_cerca = st.columns(3)
        od_eje, oi_eje, add      = st.columns(3)

        pac_data = {
            "OD_SPH": od_esf.text_input("OD ESF"), "OI_SPH": oi_esf.text_input("OI ESF"),
            "DP_Lejos": dp_lejos.text_input("DP Lejos"),
            "OD_CYL": od_cil.text_input("OD CIL"), "OI_CYL": oi_cil.text_input("OI CIL"),
            "DP_CERCA": dp_cerca.text_input("DP Cerca"),
            "OD_EJE": od_eje.text_input("OD EJE"), "OI_EJE": oi_eje.text_input("OI EJE"),
            "ADD": add.text_input("ADD")
        }

        ok = st.form_submit_button("Guardar")
    if not ok: return

    # ▶ Validaciones
    rut_limpio = limpiar_rut(rut_raw)
    if not (rut_raw and validar_rut(rut_raw)):
        st.error("RUT inválido"); return
    try:
        valor = int(valor_raw)
        edad  = int(edad_raw)
    except ValueError:
        st.error("Edad y Valor deben ser números enteros"); return

    rut_fmt = formatear_rut(rut_limpio)
    nombre  = nombre_raw.title().strip()

    # ▶ Alta / actualización
    venta = {
        "RUT": rut_fmt, "Nombre": nombre, "Edad": edad, "Teléfono": telefono,
        "Tipo_Lente": tipo_lente, "Armazon": armazon, "Cristales": cristales,
        "Valor": valor, "FORMA_PAGO": forma_pago, "Última_visita": pd.to_datetime(fecha)
    } | pac_data

    idx = df.index[df["RUT"] == rut_fmt].tolist()
    if idx:                      # existente → añadimos venta (nueva fila)
        df = pd.concat([df, pd.DataFrame([venta])], ignore_index=True)
    else:                        # paciente nuevo
        df = pd.concat([df, pd.DataFrame([venta])], ignore_index=True)

    guardar_df(df)
    st.success("Venta registrada ✅")
    st.rerun()

def pantalla_pacientes(df):
    st.header("🧑‍⚕️ Pacientes")
    if df.empty:
        st.info("No hay pacientes registrados"); return
    # resumen por paciente + PDF
    for rut, grp in df.groupby("RUT"):
        pac = grp.iloc[-1]                          # último registro ↔ datos actuales
        with st.expander(f"{pac['Nombre']}  –  {rut}"):
            st.write("Última visita:", pac["Última_visita"].date())
            st.write("Teléfono:", pac["Teléfono"])
            st.write("Historial de ventas:")
            st.dataframe(grp[["Última_visita","Tipo_Lente","Valor","FORMA_PAGO"]])
            # receta si existe
            if pac[COLUMNAS_OPT[0]]:    # tiene ESF
                if st.button("📄 Generar PDF", key=f"pdf_{rut}"):
                    pdf = pdf_receta(pac)
                    st.download_button("Descargar receta",
                        data=pdf, file_name=f"Receta_{pac['Nombre']}.pdf",
                        mime="application/pdf", key=f"dwn_{rut}")

# ╔════════════ MAIN ════════════╗
def main():
    header()
    df = cargar_datos()

    menu = st.sidebar.radio("Menú", ["Inicio","Registrar venta","Pacientes"])
    if menu == "Inicio":
        pantalla_inicio(df)
    elif menu == "Registrar venta":
        pantalla_registrar(df.copy())   # pasamos copia para evitar caché write-error
    else:
        pantalla_pacientes(df)

    st.sidebar.markdown("---")
    st.sidebar.write("BMA Ópticas © 2025")

if __name__ == "__main__":
    main()
  
