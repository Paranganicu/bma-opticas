# ▒▒▒ app.py  (BMA Ópticas v3.0) ▒▒▒
import os, re, uuid, logging, datetime as dt
from io import BytesIO
from typing import Dict, Any

import pandas as pd
import streamlit as st
from html import escape
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import magic  # ok en Streamlit Cloud

# ─────────── CONFIG GLOBAL ───────────
st.set_page_config(page_title="BMA Ópticas", page_icon="👓", layout="wide")
logging.basicConfig(filename="app.log",
                    level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")

COLUMNAS_RECETA = [
    "OD_SPH","OD_CYL","OD_EJE",
    "OI_SPH","OI_CYL","OI_EJE",
    "DP_Lejos","DP_CERCA","ADD"
]
MIME_EXCEL = {
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
}

# ─────────── UTILIDADES ───────────
def validar_rut(rut:str)->bool:
    rut = rut.upper().replace('.','').replace('-','')
    if not re.fullmatch(r'\d{7,8}[0-9K]', rut):
        return False
    cuerpo, dv = rut[:-1], rut[-1]
    s, m = 0,2
    for c in reversed(cuerpo):
        s += int(c)*m
        m = 2 if m==7 else m+1
    dv_calc = 11-(s%11); dv_calc = {10:'K',11:'0'}.get(dv_calc,str(dv_calc))
    return dv == dv_calc

def enmascarar_rut(rut:str)->str:
    if '-' not in rut: return rut
    c,d = rut.split('-')
    return (c[:-4]+'****' if len(c)>4 else c)+'-'+d

def es_excel(path:str)->bool:
    try: return magic.from_file(path, mime=True) in MIME_EXCEL
    except: return False

# ─────────── DATAFRAME ───────────
@st.cache_data(ttl=3600)
def cargar_df()->pd.DataFrame:
    if not os.path.exists('Pacientes.xlsx'): return pd.DataFrame()
    if not es_excel('Pacientes.xlsx'): return pd.DataFrame()
    df = pd.read_excel('Pacientes.xlsx').convert_dtypes()
    df.columns = df.columns.str.strip()
    if 'Última_visita' in df: df['Última_visita'] = pd.to_datetime(df['Última_visita'],errors='coerce')
    if 'Valor'         in df: df['Valor'] = pd.to_numeric(df['Valor'], errors='coerce').fillna(0)
    return df

def guardar_df(df:pd.DataFrame):
    df.to_excel('Pacientes.xlsx', index=False)

# ─────────── PDF RECETA ───────────
def pdf_receta(p:Dict[str,Any])->BytesIO:
    tmp,buf=f"tmp_{uuid.uuid4()}.pdf",BytesIO()
    c = canvas.Canvas(tmp, pagesize=letter)
    c.setTitle(f"Receta {p.get('Nombre','')}")
    c.setFont("Helvetica-Bold",16); c.drawString(72,750,"BMA Ópticas – Receta")
    c.setFont("Helvetica",12)
    c.drawString(72,730,f"Paciente: {escape(p.get('Nombre',''))}")
    c.drawString(72,712,f"RUT: {enmascarar_rut(p.get('Rut',''))}")
    c.drawString(400,712,dt.datetime.now().strftime('%d/%m/%Y'))
    y=680; c.setFont("Helvetica-Bold",12); c.drawString(72,y,"OD / OI   ESF   CIL   EJE"); y-=20
    c.setFont("Helvetica",12)
    c.drawString(72,y,f"OD: {p.get('OD_SPH','')}  {p.get('OD_CYL','')}  {p.get('OD_EJE','')}")
    y-=20
    c.drawString(72,y,f"OI: {p.get('OI_SPH','')}  {p.get('OI_CYL','')}  {p.get('OI_EJE','')}")
    y-=30
    for lbl in ("DP_Lejos","DP_CERCA","ADD"):
        if p.get(lbl): c.drawString(72,y,f"{lbl}: {p[lbl]}"); y-=18
    c.line(400,100,520,100); c.drawString(430,85,"Firma")
    c.save(); buf.write(open(tmp,'rb').read()); os.remove(tmp); buf.seek(0); return buf
  # ▒▒▒ 2/3  (app.py continuación) ▒▒▒
# ─────────── UI HEADER ───────────
def header():
    st.image("logo.png", use_container_width=True)
    st.markdown("<h2 style='text-align:center'>👓 Sistema de Gestión BMA Ópticas</h2>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align:center;color:gray'>Cuidamos tus ojos, cuidamos de ti</h4>", unsafe_allow_html=True)

# ─────────── FORM VENTA (único punto de entrada) ───────────
def registrar_venta(df:pd.DataFrame):
    st.header("💰 Registrar venta")
    with st.form(key="venta_form"):
        c1,c2 = st.columns(2)
        with c1:
            rut   = st.text_input("RUT* (con puntos y guion)")
            nombre= st.text_input("Nombre*", placeholder="Juan Pérez")
            edad  = st.number_input("Edad*",0,120,step=1,format="%d")
            tel   = st.text_input("Teléfono")
        with c2:
            tipo  = st.selectbox("Tipo de lente",["Monofocal","Bifocal","Progresivo"])
            arma  = st.text_input("Armazón")
            valo  = st.number_input("Valor venta",0,step=1000,format="%d")
            pago  = st.selectbox("Forma de pago",["Efectivo","Tarjeta","Transferencia"])
        st.markdown("##### Parámetros ópticos")
        co1,co2,co3 = st.columns(3)
        with co1:
            od_sph = st.text_input("OD ESF"); oi_sph = st.text_input("OI ESF")
        with co2:
            od_cyl = st.text_input("OD CIL"); oi_cyl = st.text_input("OI CIL")
        with co3:
            od_eje = st.text_input("OD EJE"); oi_eje = st.text_input("OI EJE")
        dp_lej = st.text_input("DP Lejos"); dp_cer = st.text_input("DP Cerca")
        adda   = st.text_input("ADD")
        ok = st.form_submit_button("Guardar")

    if not ok: return df
    if not (rut and nombre and validar_rut(rut)):
        st.error("RUT o nombre inválido"); return df

    # normalizar
    nombre = ' '.join(w.capitalize() for w in nombre.split())
    rut = rut.upper()
    hoy = dt.datetime.now()

    # Si existe, actualizo; si no, creo
    match = df["Rut"].astype(str).str.upper() == rut
    if match.any():
        idx = df[match].index[0]
        df.loc[idx,"Última_visita"] = hoy
        df.loc[idx,"Valor"] += valo
    else:
        nueva = {
            "Rut":rut,"Nombre":nombre,"Edad":edad,"Teléfono":tel,
            "Tipo_Lente":tipo,"Armazon":arma,"Valor":valo,"FORMA_PAGO":pago,
            "Última_visita":hoy,
            "OD_SPH":od_sph,"OD_CYL":od_cyl,"OD_EJE":od_eje,
            "OI_SPH":oi_sph,"OI_CYL":oi_cyl,"OI_EJE":oi_eje,
            "DP_Lejos":dp_lej,"DP_CERCA":dp_cer,"ADD":adda
        }
        df = pd.concat([df,pd.DataFrame([nueva])], ignore_index=True)

    guardar_df(df)
    st.success("Venta registrada ✅")
    st.experimental_rerun()
    return df
  # ▒▒▒ 3/3  (app.py final) ▒▒▒
def pantalla_pacientes(df:pd.DataFrame):
    st.header("👁️ Pacientes")
    if df.empty: st.info("Sin datos"); return
    busq = st.text_input("Buscar por nombre / RUT")
    if busq:
        mask = df["Nombre"].str.contains(busq,case=False,na=False)|\
               df["Rut"].str.contains(busq,case=False,na=False)
        df = df[mask]
    for _,p in df.iterrows():
        with st.expander(f"{p['Nombre']} – {enmascarar_rut(p['Rut'])}",expanded=False):
            st.write(p.to_frame().T)
            if st.button("📄 PDF",key=f"pdf_{p['Rut']}"):
                st.download_button("Descargar receta",
                    data=pdf_receta(p),file_name=f"Receta_{p['Nombre']}.pdf",
                    mime="application/pdf",key=f"dl_{p['Rut']}")

def pantalla_inicio(df):  # resumida
    st.header("🏠 Inicio")
    if df.empty: st.info("Sube base o registra primera venta"); return
    c1,c2,c3=st.columns(3)
    c1.metric("Pacientes",len(df))
    c2.metric("Ventas",f"${df['Valor'].sum():,.0f}")
    c3.metric("Recetas",df[COLUMNAS_RECETA[0]].notna().sum())
    st.dataframe(df.tail())

def main():
    header()
    df = cargar_df()
    menu = st.sidebar.radio("Menú",["🏠 Inicio","💰 Registrar venta","👁️ Pacientes"])
    if menu=="🏠 Inicio":         pantalla_inicio(df)
    elif menu=="💰 Registrar venta": df = registrar_venta(df)
    else:                        pantalla_pacientes(df)
    st.sidebar.markdown("---")
    st.sidebar.write("BMA Ópticas © 2025")

if __name__=="__main__":
    main()
