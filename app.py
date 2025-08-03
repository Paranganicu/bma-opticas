# ───────────────────── BMA ÓPTICAS  v2.2 ─────────────────────
import os, re, uuid, logging, datetime as dt
from io import BytesIO
from typing import Dict, Any

import pandas as pd
import streamlit as st
from html import escape
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import magic  # ok en Streamlit Cloud

# ───── Config global ─────────────────────────────────────────
st.set_page_config(page_title="BMA Ópticas 👓", page_icon="👓", layout="wide")
logging.basicConfig(filename="app.log",
                    level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")

COLUMNAS_OPTICAS = [
    "OD_SPH", "OD_CYL", "OD_EJE",
    "OI_SPH", "OI_CYL", "OI_EJE",
    "DP_Lejos", "DP_CERCA", "ADD"
]
MIME_VALIDOS = [
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
]

# ───── Validaciones y helpers ────────────────────────────────
def limpiar_rut(num_rut: str) -> str | None:
    """
    Convierte 123456785 -> 12.345.678-5  (o None si no es válido)
    Acepta números + K/k como DV.
    """
    num_rut = re.sub(r"[^0-9kK]", "", num_rut)  # solo cifras y K
    if not num_rut:
        return None
    cuerpo, dv = num_rut[:-1], num_rut[-1].upper()
    if len(cuerpo) < 7 or len(cuerpo) > 8:
        return None
    # cálculo DV
    suma, mult = 0, 2
    for c in reversed(cuerpo):
        suma += int(c) * mult
        mult = 2 if mult == 7 else mult + 1
    dv_calc = 11 - (suma % 11)
    dv_calc = {10: "K", 11: "0"}.get(dv_calc, str(dv_calc))
    if dv != dv_calc:
        return None
    cuerpo_form = f"{int(cuerpo):,}".replace(",", ".")  # puntos miles
    return f"{cuerpo_form}-{dv}"

def enmascarar_rut(rut: str) -> str:
    try:
        cuerpo, dv = rut.split("-")
        return f"{cuerpo[:-4]}****-{dv}" if len(cuerpo) > 4 else rut
    except ValueError:
        return rut

def capitalizar(nombre: str) -> str:
    return " ".join(p.capitalize() for p in nombre.strip().split())

def es_excel_valido(path: str) -> bool:
    try:
        return magic.from_file(path, mime=True) in MIME_VALIDOS
    except Exception as e:
        logging.error(f"MIME error: {e}")
        return False

# ───── Datos ─────────────────────────────────────────────────
@st.cache_data(ttl=3600, hash_funcs={pd.DataFrame: lambda _: None})
def cargar_datos() -> pd.DataFrame:
    # si no existe, creamos la base vacía
    if not os.path.exists("Pacientes.xlsx"):
        pd.DataFrame().to_excel("Pacientes.xlsx", index=False)
    if not es_excel_valido("Pacientes.xlsx"):
        st.error("❌ 'Pacientes.xlsx' no es un Excel válido")
        return pd.DataFrame()

    df = pd.read_excel("Pacientes.xlsx")
    df.columns = df.columns.str.strip()

    if "Última_visita" in df.columns:
        df["Última_visita"] = pd.to_datetime(df["Última_visita"], errors="coerce")
    if "Valor" in df.columns:
        df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce").fillna(0)

    # Asegurar columnas ópticas como texto
    for col in COLUMNAS_OPTICAS:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).str.strip()

    return df

def guardar_datos(df: pd.DataFrame):
    try:
        df.to_excel("Pacientes.xlsx", index=False)
        logging.info("Base actualizada")
    except Exception as e:
        st.warning(f"⚠️ No se pudo guardar en disco: {e}")

# ───── PDF  ──────────────────────────────────────────────────
def generar_pdf_receta(p: Dict[str, Any]) -> BytesIO:
    tmp, buf = f"tmp_{uuid.uuid4()}.pdf", BytesIO()
    c = canvas.Canvas(tmp, pagesize=letter)
    try:
        c.setTitle(f"Receta {p.get('Nombre','')}")
        c.setFont("Helvetica-Bold", 16)
        c.drawString(72, 750, "BMA Ópticas – Receta")
        c.setFont("Helvetica", 12)
        c.drawString(72, 730, f"Paciente: {escape(p.get('Nombre',''))}")
        c.drawString(72, 712, f"RUT: {enmascarar_rut(p.get('Rut',''))}")
        c.drawString(400, 712, dt.datetime.now().strftime("%d/%m/%Y"))

        y = 680
        c.setFont("Helvetica-Bold", 12)
        c.drawString(72, y, "OD / OI    ESF   CIL   EJE")
        y -= 20
        c.setFont("Helvetica", 12)
        c.drawString(
            72, y,
            f"OD: {p.get('OD_SPH','')}  {p.get('OD_CYL','')}  {p.get('OD_EJE','')}"
        )
        y -= 20
        c.drawString(
            72, y,
            f"OI: {p.get('OI_SPH','')}  {p.get('OI_CYL','')}  {p.get('OI_EJE','')}"
        )
        y -= 30
        for lbl in ["DP_Lejos", "DP_CERCA", "ADD"]:
            if p.get(lbl):
                c.drawString(72, y, f"{lbl}: {p[lbl]}")
                y -= 18
        c.line(400, 100, 520, 100)
        c.drawString(430, 85, "Firma Óptico")
        c.save()

        with open(tmp, "rb") as fp:
            buf.write(fp.read())
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    buf.seek(0)
    return buf

# ───── UI helpers ────────────────────────────────────────────
def header():
    st.image("logo.png", use_container_width=True)
    st.markdown(
        "<h2 style='text-align:center;'>👓 Sistema de Gestión BMA Ópticas</h2>",
        unsafe_allow_html=True
    )
    st.markdown(
        "<h4 style='text-align:center;color:gray;'>Cuidamos tus ojos, cuidamos de ti</h4>",
        unsafe_allow_html=True
    )

# ───── Pantallas ─────────────────────────────────────────────
def pantalla_inicio(df: pd.DataFrame):
    st.header("🏠 Inicio")
    c1, c2, c3 = st.columns(3)
    c1.metric("Pacientes", len(df))
    c2.metric("Con receta",
              df["OD_SPH"].notna().sum() if "OD_SPH" in df else 0)
    c3.metric("Ventas",
              f"${df['Valor'].sum():,.0f}" if "Valor" in df else "$0")

def registrar_venta(df: pd.DataFrame) -> pd.DataFrame:
    st.header("💰 Registrar venta")
    with st.form("venta", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            rut_raw = st.text_input("RUT* (sólo números y K)")
            nombre  = st.text_input("Nombre*", max_chars=60)
            edad    = st.number_input("Edad*", min_value=0, max_value=120, step=1)
            telefono= st.text_input("Teléfono")
        with c2:
            tipo_lente = st.selectbox("Tipo de lente",
                                      ["Monofocal", "Bifocal", "Progresivo"])
            armazon     = st.text_input("Armazón")
            cristales   = st.text_input("Cristales")
            valor       = st.number_input("Valor venta*", min_value=0, step=1000)
            f_pago      = st.selectbox("Forma de pago",
                                       ["Efectivo", "T. Crédito", "T. Débito"])
            fecha       = st.date_input("Fecha de venta", dt.date.today())

        st.markdown("#### Datos ópticos (opcional)")
        co1, co2, co3 = st.columns(3)
        with co1:
            od_sph = st.text_input("OD ESF")
            od_cyl = st.text_input("OD CIL")
            od_eje = st.text_input("OD EJE")
        with co2:
            oi_sph = st.text_input("OI ESF")
            oi_cyl = st.text_input("OI CIL")
            oi_eje = st.text_input("OI EJE")
        with co3:
            dp_lejos = st.text_input("DP Lejos")
            dp_cerca = st.text_input("DP Cerca")
            add      = st.text_input("ADD")

        ok = st.form_submit_button("Guardar")

    if not ok:
        return df

    rut_fmt = limpiar_rut(rut_raw)
    if rut_fmt is None or not nombre.strip():
        st.error("Debes ingresar RUT válido y nombre")
        return df

    nombre = capitalizar(nombre)

    # ----- alta o venta -----
    existe = "Rut" in df.columns and df["Rut"].eq(rut_fmt).any()
    fila_base = {
        "Rut": rut_fmt, "Nombre": nombre, "Edad": edad, "Teléfono": telefono,
        "Tipo_Lente": tipo_lente, "Armazon": armazon, "Cristales": cristales,
        "Valor": valor, "FORMA_PAGO": f_pago, "Última_visita": fecha,
        "OD_SPH": od_sph, "OD_CYL": od_cyl, "OD_EJE": od_eje,
        "OI_SPH": oi_sph, "OI_CYL": oi_cyl, "OI_EJE": oi_eje,
        "DP_Lejos": dp_lejos, "DP_CERCA": dp_cerca, "ADD": add
    }

    df = pd.concat([df, pd.DataFrame([fila_base])], ignore_index=True)
    guardar_datos(df)
    st.success("Venta registrada ✅")
    st.rerun()  # recarga pantalla
    return df

def pantalla_pacientes(df: pd.DataFrame):
    st.header("👁️ Pacientes")
    if df.empty:
        st.info("No hay datos")
        return

    for idx, g in df.groupby("Rut"):
        pac = g.iloc[-1]
        with st.expander(f"{pac['Nombre']} – {enmascarar_rut(pac['Rut'])}",
                         expanded=False):
            st.write("##### Historial ventas")
            st.dataframe(
                g[["Última_visita", "Tipo_Lente", "Valor", "FORMA_PAGO"]]
                .sort_values("Última_visita", ascending=False)
            )

            if pac["OD_SPH"] or pac["OI_SPH"]:
                st.write("##### Última receta")
                st.write(pac[COLUMNAS_OPTICAS[:6]].to_frame().T)

                if st.button("📄 PDF", key=f"pdf_{idx}"):
                    pdf = generar_pdf_receta(pac)
                    st.download_button(
                        "Descargar",
                        data=pdf,
                        file_name=f"Receta_{pac['Nombre']}.pdf",
                        mime="application/pdf",
                        key=f"dl_{idx}"
                    )

# ───── Main ────────────────────────────────────────────────
def main():
    header()
    df = cargar_datos()

    pagina = st.sidebar.radio(
        "Menú",
        ["🏠 Inicio", "💰 Registrar venta", "👁️ Pacientes"]
    )

    if pagina == "🏠 Inicio":
        pantalla_inicio(df)
    elif pagina == "💰 Registrar venta":
        df = registrar_venta(df)
    else:
        pantalla_pacientes(df)

    st.sidebar.markdown("---")
    st.sidebar.caption("BMA Ópticas © 2025")

if __name__ == "__main__":
    main()
