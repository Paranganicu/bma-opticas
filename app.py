import os, re, uuid, logging, datetime as dt
from io import BytesIO
from typing import Dict, Any

import pandas as pd
import streamlit as st
from html import escape
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import magic                       # ok en Streamlit Cloud

# ─────────────────── CONFIG GLOBAL ───────────────────
st.set_page_config(page_title="BMA Ópticas", page_icon="👓", layout="wide")
logging.basicConfig(filename="app.log",
                    level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")

COLUMNAS_OPTICAS = ["OD_SPH","OD_CYL","OD_EJE","OI_SPH","OI_CYL","OI_EJE",
                    "DP_Lejos","DP_CERCA","ADD"]
MIME_VALIDOS = ["application/vnd.ms-excel",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]

# ─────────────────── UTILIDADES ───────────────────
def validar_rut_completo(rut: str) -> bool:
    try:
        rut = rut.upper().replace(".","").replace("-","")
        if not re.match(r"^[0-9]{7,8}[0-9K]$", rut):
            return False
        cuerpo, dv = rut[:-1], rut[-1]
        suma, fac = 0, 2
        for c in reversed(cuerpo):
            suma += int(c) * fac
            fac = 2 if fac == 7 else fac + 1
        dv_calc = 11 - (suma % 11)
        dv_calc = {10:"K", 11:"0"}.get(dv_calc, str(dv_calc))
        return dv == dv_calc
    except Exception as e:
        logging.error(f"valRUT {rut}: {e}")
        return False

def enmascarar_rut(rut: str) -> str:
    if "-" not in rut: return rut
    cuerpo, dv = rut.split("-")
    if len(cuerpo) > 4: cuerpo = f"{cuerpo[:-4]}****"
    return f"{cuerpo}-{dv}"

def es_excel_valido(path:str)->bool:
    try:  return magic.from_file(path, mime=True) in MIME_VALIDOS
    except Exception as e:
        logging.error(f"MIME: {e}"); return False

# ─────────────────── DATA ───────────────────
@st.cache_data(ttl=3600, hash_funcs={pd.DataFrame:lambda _:None})
def cargar_datos()->pd.DataFrame:
    if not os.path.exists("Pacientes.xlsx"):
        st.error("❌ Falta 'Pacientes.xlsx'"); return pd.DataFrame()
    if not es_excel_valido("Pacientes.xlsx"):
        st.error("❌ El archivo no es Excel válido"); return pd.DataFrame()
    try:
        df = pd.read_excel("Pacientes.xlsx").copy()
        df.columns = df.columns.str.strip()
        if "Rut" in df.columns:
            df["Rut_Válido"] = df["Rut"].astype(str).apply(validar_rut_completo)
            if not df["Rut_Válido"].all():
                st.warning("⚠️ Hay RUTs inválidos en la base")
        if "Última_visita" in df.columns:
            df["Última_visita"] = pd.to_datetime(df["Última_visita"], errors="coerce")
        if "Valor" in df.columns:
            df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce").fillna(0)
        for col in COLUMNAS_OPTICAS:
            if col in df.columns:
                df[col] = df[col].fillna("").astype(str).str.strip()
        logging.info(f"Cargados {len(df)} registros")
        return df
    except Exception as e:
        logging.critical(e, exc_info=True)
        st.error(f"❌ Error crítico cargando datos: {e}")
        return pd.DataFrame()

# ─────────────────── PDF ───────────────────
def generar_pdf_receta(pac:Dict[str,Any])->BytesIO:
    tmp, buf = f"tmp_{uuid.uuid4()}.pdf", BytesIO()
    try:
        c = canvas.Canvas(tmp, pagesize=letter)
        c.setTitle(f"Receta {pac.get('Nombre','')}")
        c.setFont("Helvetica-Bold", 16); c.drawString(72,750,"BMA Ópticas – Receta")
        c.setFont("Helvetica",12)
        c.drawString(72,730,f"Paciente: {escape(pac.get('Nombre',''))}")
        c.drawString(72,712,f"RUT: {enmascarar_rut(pac.get('Rut',''))}")
        c.drawString(400,712,dt.datetime.now().strftime("%d/%m/%Y"))
        y = 680
        c.setFont("Helvetica-Bold",12); c.drawString(72,y,"OD / OI   ESF   CIL   EJE"); y -= 20
        c.setFont("Helvetica",12)
        c.drawString(72,y,f"OD: {pac.get('OD_SPH','')}  {pac.get('OD_CYL','')}  {pac.get('OD_EJE','')}")
        y -= 20
        c.drawString(72,y,f"OI: {pac.get('OI_SPH','')}  {pac.get('OI_CYL','')}  {pac.get('OI_EJE','')}")
        y -= 30
        for label in ["DP_Lejos","DP_CERCA","ADD"]:
            if pac.get(label): c.drawString(72,y,f"{label}: {pac[label]}"); y-=18
        c.line(400,100,520,100); c.drawString(430,85,"Firma Óptico")
        c.save(); buf.write(open(tmp,"rb").read())
    except Exception as e:
        logging.error(f"PDF: {e}", exc_info=True)
    finally:
        if os.path.exists(tmp): os.remove(tmp)
    buf.seek(0); return buf

# ─────────────────── UI – HEADER ───────────────────
def header():
    st.image("logo.png", use_container_width=True)
    st.markdown("<h2 style='text-align:center;'>👓 Sistema de Gestión BMA Ópticas</h2>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align:center;color:gray;'>Cuidamos tus ojos, cuidamos de ti</h4>", unsafe_allow_html=True)

# ─────────────────── PANTALLAS ───────────────────
def pantalla_inicio(df:pd.DataFrame):
    st.header("🏠 Inicio")
    if df.empty:
        st.info("Carga 'Pacientes.xlsx' para empezar"); return
    c1,c2,c3 = st.columns(3)
    c1.metric("Pacientes", len(df))
    c2.metric("Con receta", df[COLUMNAS_OPTICAS[0]].notna().sum())
    c3.metric("Ventas", f"${df['Valor'].sum():,.0f}")
    st.dataframe(df.head())

def pantalla_pacientes(df:pd.DataFrame):
    st.header("👁️ Pacientes")
    if df.empty: st.warning("No hay datos"); return
    # Filtros
    with st.expander("Filtros"):
        q      = st.text_input("Nombre, RUT o Teléfono")
        tipo   = st.selectbox("Tipo lente", ["Todos"]+sorted(df["Tipo_Lente"].dropna().unique()))
        arma   = st.selectbox("Armazón", ["Todos"]+sorted(df["Armazon"].dropna().unique()))
        r_edad = st.slider("Edad", int(df["Edad"].min()), int(df["Edad"].max()),
                           (int(df["Edad"].min()), int(df["Edad"].max())))
    # Aplicar filtros
    df_f = df.copy()
    if q:
        m = (df_f["Nombre"].str.contains(q,case=False,na=False) |
             df_f["Rut"].astype(str).str.contains(q,case=False,na=False) |
             df_f["Teléfono"].astype(str).str.contains(q,case=False,na=False))
        df_f = df_f[m]
    if tipo!="Todos": df_f = df_f[df_f["Tipo_Lente"]==tipo]
    if arma!="Todos": df_f = df_f[df_f["Armazon"]==arma]
    df_f = df_f[(df_f["Edad"]>=r_edad[0]) & (df_f["Edad"]<=r_edad[1])]
    st.success(f"{len(df_f)} resultados"); st.dataframe(df_f)

    # ───── Formulario de alta ─────
    with st.expander("➕ Agregar nuevo paciente"):
        with st.form("alta_paciente", clear_on_submit=True):
            c1,c2 = st.columns(2)
            with c1:
                nombre  = st.text_input("Nombre*", max_chars=60)
                rut     = st.text_input("RUT*", max_chars=12)
                edad    = st.number_input("Edad*", 0,120,30)
                telefono= st.text_input("Teléfono")
            with c2:
                tipo_lente   = st.selectbox("Tipo de lente", ["Monofocal","Bifocal","Progresivo"])
                valor        = st.number_input("Valor venta", 0, step=1000)
                ultima_visita= st.date_input("Última visita", dt.date.today())
            ok = st.form_submit_button("Guardar")

        if ok:
            if not (nombre and rut and validar_rut_completo(rut)):
                st.error("Completa nombre y RUT válido")
            else:
                nueva = {"Nombre":nombre,"Rut":rut,"Edad":edad,"Teléfono":telefono,
                         "Tipo_Lente":tipo_lente,"Valor":valor,
                         "Última_visita":pd.to_datetime(ultima_visita)}
                df.loc[len(df)] = nueva
                try:
                    df.to_excel("Pacientes.xlsx", index=False)
                    st.success("Paciente agregado ✅")
                except Exception as e:
                    st.warning(f"No se pudo guardar en disco: {e}")
                st.experimental_rerum()

def pantalla_ventas(df:pd.DataFrame):
    st.header("💰 Ventas")
    v = df[df["Valor"]>0]
    if v.empty: st.info("Sin ventas"); return
    c1,c2,c3=st.columns(3)
    c1.metric("Total", f"${v['Valor'].sum():,.0f}")
    c2.metric("Ticket medio", f"${v['Valor'].mean():,.0f}")
    c3.metric("Transacciones", len(v))

def pantalla_reportes(df:pd.DataFrame):
    st.header("📊 Reportes")
    if df.empty: st.warning("No hay datos"); return
    v = df[df["Valor"]>0]
    if not v.empty:
        st.subheader("Ventas por tipo de lente")
        st.bar_chart(v.groupby("Tipo_Lente")["Valor"].sum())
    st.subheader("Recetas")
    con = df[df[COLUMNAS_OPTICAS[0]].notna()]
    for idx, pac in con.iterrows():
        with st.expander(f"{pac['Nombre']} – {enmascarar_rut(pac['Rut'])}"):
            st.write(pac[COLUMNAS_OPTICAS[:6]].to_frame().T)
            if st.button("📄 PDF", key=f"pdf_{idx}"):
                pdf = generar_pdf_receta(pac)
                st.download_button("Descargar", data=pdf,
                                   file_name=f"Receta_{pac['Nombre']}.pdf",
                                   mime="application/pdf", key=f"dl_{idx}")

def pantalla_alertas(df:pd.DataFrame):
    st.header("⚠️ Alertas")
    if df.empty: st.info("No hay datos"); return
    atras = df[df["Última_visita"] < dt.datetime.now()-dt.timedelta(days=365)]
    if not atras.empty:
        st.warning(f"{len(atras)} pacientes sin control >1 año")
        st.dataframe(atras[["Nombre","Última_visita","Teléfono"]])

# ─────────────────── MAIN ───────────────────
def main():
    header()
    with st.spinner("Cargando…"):
        df = cargar_datos()
    menu = st.sidebar.radio("Menú", ["🏠 Inicio","👁️ Pacientes","💰 Ventas","📊 Reportes","⚠️ Alertas"])
    if   menu=="🏠 Inicio":   pantalla_inicio(df)
    elif menu=="👁️ Pacientes": pantalla_pacientes(df)
    elif menu=="💰 Ventas":   pantalla_ventas(df)
    elif menu=="📊 Reportes": pantalla_reportes(df)
    else:                     pantalla_alertas(df)
    st.sidebar.markdown("---"); st.sidebar.write("BMA Ópticas © 2025")

if __name__ == "__main__":
    main()
