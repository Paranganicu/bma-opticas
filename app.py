# BMA Ópticas · Gestión integral 2025
# ──────────── librerías ────────────
import os, re, uuid, logging, datetime as dt
from io import BytesIO
from typing import Dict, Any

import pandas as pd
import streamlit as st
from html import escape           # para sanitizar strings en PDF
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import magic                      # ok en Streamlit Cloud

# ──────────── configuración app ────────────
st.set_page_config("BMA Ópticas", "👓", layout="wide")
logging.basicConfig(filename="app.log",
                    level=logging.INFO,
                    format="%(asctime)s • %(levelname)s • %(message)s")

COLUMNAS_OPTICAS = [
    "OD_SPH","OD_CYL","OD_EJE",
    "OI_SPH","OI_CYL","OI_EJE",
    "DP_Lejos","DP_Cerca","ADD"
]
MIME_VALIDOS = [
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
]

# ──────────── utilidades ────────────
def _validar_rut(rut: str) -> bool:
    try:
        rut = rut.upper().replace(".", "").replace("-", "")
        if not re.match(r"^[0-9]{7,8}[0-9K]$", rut):
            return False
        cuerpo, dv_txt = rut[:-1], rut[-1]
        suma, fac = 0, 2
        for c in reversed(cuerpo):
            suma += int(c) * fac
            fac = 2 if fac == 7 else fac + 1
        dv_calc = 11 - (suma % 11)
        dv_calc = {10: "K", 11: "0"}.get(dv_calc, str(dv_calc))
        return dv_txt == dv_calc
    except Exception as e:
        logging.error(f"valRUT {rut}: {e}")
        return False

def _enmascarar_rut(rut: str) -> str:
    if "-" not in rut:
        return rut
    cuerpo, dv = rut.split("-")
    if len(cuerpo) > 4:
        cuerpo = f"{cuerpo[:-4]}****"
    return f"{cuerpo}-{dv}"

def _excel_valido(path: str) -> bool:
    try:
        return magic.from_file(path, mime=True) in MIME_VALIDOS
    except Exception as e:
        logging.error(f"MIME error: {e}")
        return False

# ──────────── datos ────────────
@st.cache_data(ttl=3600, hash_funcs={pd.DataFrame: lambda _: None})
def _cargar_df() -> pd.DataFrame:
    if not os.path.exists("Pacientes.xlsx"):
        return pd.DataFrame()
    if not _excel_valido("Pacientes.xlsx"):
        st.error("❌ 'Pacientes.xlsx' no es un Excel válido")
        return pd.DataFrame()

    df = pd.read_excel("Pacientes.xlsx")
    df.columns = df.columns.str.strip()

    # Normalizaciones
    if "Última_visita" in df.columns:
        df["Última_visita"] = pd.to_datetime(df["Última_visita"], errors="coerce")
    if "Valor" in df.columns:
        df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce").fillna(0)

    for col in COLUMNAS_OPTICAS:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).str.strip()

    return df

def _guardar_df(df: pd.DataFrame):
    try:
        df.to_excel("Pacientes.xlsx", index=False)
        logging.info("Excel guardado")
    except Exception as e:
        st.warning(f"No se pudo guardar en disco: {e}")
        logging.error(f"Save error: {e}")

# ──────────── PDF receta ────────────
def _pdf_receta(p: Dict[str, Any]) -> BytesIO:
    tmp = f"tmp_{uuid.uuid4()}.pdf"
    buf = BytesIO()
    try:
        c = canvas.Canvas(tmp, pagesize=letter)
        c.setTitle(f"Receta {p.get('Nombre','')}")
        c.setFont("Helvetica-Bold", 15)
        c.drawString(72, 750, "BMA Ópticas – Receta")
        c.setFont("Helvetica", 12)
        c.drawString(72, 730, f"Paciente: {escape(p.get('Nombre',''))}")
        c.drawString(72, 712, f"RUT: {_enmascarar_rut(p.get('Rut',''))}")
        c.drawString(400, 712, dt.datetime.now().strftime("%d/%m/%Y"))
        y = 680
        c.setFont("Helvetica-Bold", 12); c.drawString(72, y, "OD / OI   ESF   CIL   EJE"); y -= 20
        c.setFont("Helvetica", 12)
        c.drawString(72, y, f"OD: {p.get('OD_SPH','')}  {p.get('OD_CYL','')}  {p.get('OD_EJE','')}")
        y -= 20
        c.drawString(72, y, f"OI: {p.get('OI_SPH','')}  {p.get('OI_CYL','')}  {p.get('OI_EJE','')}")
        y -= 30
        for lbl, nom in [("DP Lejos", "DP_Lejos"), ("DP Cerca", "DP_Cerca"), ("ADD", "ADD")]:
            if p.get(nom): c.drawString(72, y, f"{lbl}: {p[nom]}"); y -= 18
        c.line(400, 100, 520, 100); c.drawString(435, 85, "Firma Óptico")
        c.save(); buf.write(open(tmp, "rb").read())
    except Exception as e:
        logging.error(f"PDF: {e}", exc_info=True)
    finally:
        if os.path.exists(tmp): os.remove(tmp)
    buf.seek(0); return buf

# ──────────── UI comunes ────────────
def _header():
    st.image("logo.png", use_container_width=True)
    st.markdown("<h2 style='text-align:center;'>👓 Sistema de Gestión BMA Ópticas</h2>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align:center;color:gray;'>Cuidamos tus ojos, cuidamos de ti</h4>", unsafe_allow_html=True)

def _form_venta(df: pd.DataFrame):
    """Formulario unificado Paciente + Receta + Venta"""
    st.markdown("### ➕ Registrar Venta")
    with st.form("form_venta", clear_on_submit=True):
        col_p1, col_p2 = st.columns(2)
        # ─ Paciente ─
        with col_p1:
            rut_in = st.text_input("RUT* (con puntos y guion)")
            if rut_in and _validar_rut(rut_in):
                # autocompletar
                existe = df[df["Rut"].str.upper() == rut_in.upper()]
                if not existe.empty:
                    pac_pre = existe.iloc[-1]
                else:
                    pac_pre = {}
            else:
                pac_pre = {}

        with col_p1:
            nom_in = st.text_input("Nombre*", value=pac_pre.get("Nombre", "")).title()
            edad_in = st.number_input("Edad*", min_value=0, max_value=120,
                                      value=int(pac_pre.get("Edad", 0)) if pac_pre else None,
                                      placeholder="Edad")
            tel_in  = st.text_input("Teléfono", value=pac_pre.get("Teléfono", ""))

        # ─ Venta ─
        with col_p2:
            tipo_lente = st.selectbox("Tipo de lente", ["Monofocal", "Bifocal", "Progresivo"],
                                      index=["Monofocal", "Bifocal", "Progresivo"].index(
                                          pac_pre.get("Tipo_Lente", "Monofocal"))
                                      if pac_pre else 0)
            arma_in = st.text_input("Armazón", value=pac_pre.get("Armazon", ""))
            crist_in = st.text_input("Cristales", value=pac_pre.get("Tipo_Cxs", ""))
            valor_in = st.number_input("Valor venta ($)", min_value=0, step=1000,
                                       value=int(pac_pre.get("Valor", 0)) if pac_pre else 0)
            forma_pago = st.selectbox("Forma de pago",
                                      ["Efectivo", "Tarjeta", "Transferencia", "Otro"],
                                      index=0)
            fecha_venta = st.date_input("Fecha venta", dt.date.today())

        st.markdown("---")
        # ─ Receta ─
        st.markdown("**Receta (opcional)**")
        r1, r2, r3, r4 = st.columns(4)
        with r1:
            od_sph = st.text_input("OD ESF", value=pac_pre.get("OD_SPH", ""))
            od_cyl = st.text_input("OD CIL", value=pac_pre.get("OD_CYL", ""))
            od_eje = st.text_input("OD EJE", value=pac_pre.get("OD_EJE", ""))
        with r2:
            oi_sph = st.text_input("OI ESF", value=pac_pre.get("OI_SPH", ""))
            oi_cyl = st.text_input("OI CIL", value=pac_pre.get("OI_CYL", ""))
            oi_eje = st.text_input("OI EJE", value=pac_pre.get("OI_EJE", ""))
        with r3:
            dp_le = st.text_input("DP Lejos", value=pac_pre.get("DP_Lejos", ""))
            dp_ce = st.text_input("DP Cerca", value=pac_pre.get("DP_Cerca", ""))
            add   = st.text_input("ADD", value=pac_pre.get("ADD", ""))
        with r4:
            st.empty()

        ok = st.form_submit_button("💾 Guardar venta")

    if not ok:
        return df  # sin cambios

    # ─ Validaciones mínimas ─
    if not _validar_rut(rut_in):
        st.error("RUT inválido"); return df
    if not nom_in:
        st.error("Nombre es obligatorio"); return df

    # ─ Normalizar ─
    rut_norm = rut_in.upper()
    nom_norm = nom_in.title().strip()

    # ─ Insert/update paciente ─
    mask = df["Rut"].str.upper() == rut_norm
    if mask.any():
        idx = mask.idxmax()
    else:
        idx = len(df)
    df.loc[idx, ["Nombre", "Rut", "Edad", "Teléfono"]] = [
        nom_norm, rut_norm, edad_in, tel_in
    ]

    # ─ Rellenar campos restantes ─
    df.loc[idx, ["Tipo_Lente", "Armazon", "Tipo_Cxs"]] = [
        tipo_lente, arma_in, crist_in
    ]
    df.loc[idx, ["Valor", "FORMA_PAGO", "Última_visita"]] = [
        valor_in, forma_pago, pd.to_datetime(fecha_venta)
    ]
    df.loc[idx, COLUMNAS_OPTICAS] = [
        od_sph, od_cyl, od_eje, oi_sph, oi_cyl, oi_eje, dp_le, dp_ce, add
    ]

    _guardar_df(df)
    st.success("Venta registrada ✅")
    return df

# ──────────── vista por paciente ────────────
def _vista_pacientes(df: pd.DataFrame):
    st.markdown("## 👁️ Pacientes & Ventas")
    if df.empty:
        st.info("No hay datos"); return

    for rut, grupo in df.groupby("Rut"):
        pac = grupo.iloc[-1]   # último registro
        with st.expander(f"{pac['Nombre']} – {_enmascarar_rut(rut)}"):
            col1, col2 = st.columns([1, 2])
            with col1:
                st.write("**Datos básicos**")
                st.write(f"Edad: {pac.get('Edad','')}")
                st.write(f"Tel:  {pac.get('Teléfono','')}")
                st.write(f"Última visita: {pac['Última_visita'].date()}")
                st.write(f"Total gastado: ${grupo['Valor'].sum():,.0f}")
                if st.button("➕ Nueva venta", key=f"nv_{rut}"):
                    st.session_state["rut_edicion"] = rut
                    st.experimental_set_query_params(tab="ventas")
            with col2:
                st.write("**Historial de ventas**")
                st.dataframe(
                    grupo[["Última_visita","Tipo_Lente","Valor","FORMA_PAGO"]]
                    .sort_values("Última_visita", ascending=False)
                )
                # Receta PDF
                if pac[COLUMNAS_OPTICAS[0]]:
                    if st.button("📄 Última receta (PDF)", key=f"rec_{rut}"):
                        pdf = _pdf_receta(pac)
                        st.download_button("Descargar",
                                           data=pdf,
                                           file_name=f"Receta_{pac['Nombre']}.pdf",
                                           mime="application/pdf",
                                           key=f"dl_{rut}")

# ──────────── Main ────────────
def main():
    _header()
    df = _cargar_df()

    # pestaña en URL (permite volver)
    params = st.experimental_get_query_params()
    default_tab = params.get("tab", ["inicio"])[0]

    tab = st.sidebar.radio(
        "Menú",
        ["inicio", "ventas", "pacientes"],
        index=["inicio","ventas","pacientes"].index(default_tab),
        format_func=lambda x: {"inicio":"🏠 Inicio",
                               "ventas":"💰 Registrar venta",
                               "pacientes":"👁️ Pacientes"}[x]
    )

    if tab == "inicio":
        st.header("🏠 Dashboard")
        _vista_pacientes(df.head(5))   # mini preview
    elif tab == "ventas":
        df = _form_venta(df)           # puede modificar df
    else:
        _vista_pacientes(df)

    # guardar df en sesión para no releer cada cambio
    st.session_state["datos"] = df

if __name__ == "__main__":
    main()
