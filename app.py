import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="Dashboard de Guías", page_icon="📋", layout="wide")

# -----------------------------
# Estilo
# -----------------------------
st.markdown("""
<style>
.block-container {max-width:1500px; padding-top:1rem;}
.kpi {border:1px solid #dfe7f1; border-radius:14px; padding:16px; background:#f8fbff;}
.kpi-title {font-size:13px;color:#596b80;}
.kpi-value {font-size:30px;font-weight:800;color:#10233f;}
.kpi-sub {font-size:12px;color:#6c7b8c;}
.section {border:1px solid #e1e8f0;border-radius:14px;padding:14px;margin:10px 0 16px;}
</style>
""", unsafe_allow_html=True)

def norm(x):
    s=str(x).strip().lower()
    for a,b in {"á":"a","é":"e","í":"i","ó":"o","ú":"u","ñ":"n","_":" ","-":" "}.items():
        s=s.replace(a,b)
    return " ".join(s.split())

def find_col(df, candidates):
    cols=list(df.columns)
    for cand in candidates:
        for col in cols:
            if norm(col)==norm(cand):
                return col
    for cand in candidates:
        for col in cols:
            if norm(cand) in norm(col):
                return col
    return None

def detect(df):
    return {
        "guia": find_col(df, [
            "key","guia","guía","nro guia","nro. guia",
            "numero guia","número de guía","guia de remision","guía de remisión"
        ]),
        "fecha": find_col(df, [
            "fecha","fecha salida","fecha despacho","fecha de salida",
            "fecha entrega","created at","timestamp"
        ]),
        "estado": find_col(df, [
            "estado","estatus","status","estado guia","estado de guia",
            "estado de guía"
        ]),
        "sede": find_col(df, [
            "sede","almacen","almacén","almacen destino",
            "centro","centro de costo","local"
        ]),
        "encargado": find_col(df, [
            "encargado","responsable","supervisor","solicitante",
            "responsable de despacho","encargado de despacho"
        ])
    }

def read_file(upload):
    if upload.name.lower().endswith(".csv"):
        return pd.read_csv(upload)
    xls=pd.ExcelFile(upload)
    best=xls.sheet_names[0]
    rows=-1
    for sh in xls.sheet_names:
        try:
            t=pd.read_excel(upload,sheet_name=sh)
            n=len(t.dropna(how="all"))
            if n>rows:
                rows=n
                best=sh
        except:
            pass
    return pd.read_excel(upload,sheet_name=best)

def clean(df):
    df=df.copy()
    df.columns=[str(x).strip() for x in df.columns]
    c=detect(df)

    # Guía como identificador único
    if c["guia"]:
        df["_guia"]=df[c["guia"]].astype(str).str.strip()
        df=df[(df["_guia"]!="") & (df["_guia"].str.lower()!="nan")]
    else:
        st.warning("No se encontró una columna de Guía/KEY. Se utilizará cada registro como guía.")
        df["_guia"]=df.index.astype(str)

    if c["fecha"]:
        df["_fecha"]=pd.to_datetime(df[c["fecha"]], errors="coerce", dayfirst=True)
        df["_mes"]=df["_fecha"].dt.to_period("M").astype(str)
    else:
        df["_fecha"]=pd.NaT
        df["_mes"]="Sin fecha"

    for key in ["estado","sede","encargado"]:
        if c[key]:
            df[f"_{key}"]=df[c[key]].astype(str).str.strip()
            df.loc[df[f"_{key}"].str.lower().isin(["","nan","none"]), f"_{key}"]="Sin dato"
        else:
            df[f"_{key}"]="Sin dato"

    return df,c

def kpi(title,value,sub):
    st.markdown(
        f"""<div class="kpi">
        <div class="kpi-title">{title}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-sub">{sub}</div>
        </div>""",
        unsafe_allow_html=True
    )

def fmt(v):
    return f"{int(round(v)):,}".replace(",", ".")

def compare(old_df,new_df):
    old=old_df["_guia"].nunique()
    new=new_df["_guia"].nunique()
    diff=new-old
    pct=None if old==0 else diff/old*100
    return old,new,diff,pct

# -----------------------------
# Carga
# -----------------------------
st.title("📋 Matriz de Guías por Sede")
st.caption("Guías · Estado · Sede · Encargados · Evolución mensual · Comparación de cargas")

with st.sidebar:
    st.header("📂 Cargar archivos")
    uploads=st.file_uploader(
        "Excel de despachos",
        type=["xlsx","xls","csv"],
        accept_multiple_files=True
    )
    st.divider()
    st.write("**1 archivo:** análisis actual")
    st.write("**2 archivos:** anterior vs. actual")
    st.write("El sistema cuenta **guías únicas**, no filas.")

if not uploads:
    st.info("Carga tu Excel para comenzar.")
    st.stop()

datasets=[]
for up in uploads[:2]:
    try:
        raw=read_file(up)
        df,c=clean(raw)
        datasets.append((up.name,df,c))
    except Exception as e:
        st.error(f"No se pudo leer {up.name}: {e}")

if not datasets:
    st.stop()

# Primero = anterior si hay dos; último = actual
actual_name,df,c=datasets[-1]

# -----------------------------
# Filtros
# -----------------------------
st.markdown('<div class="section">', unsafe_allow_html=True)
st.subheader("🔎 Filtros")

f1,f2,f3,f4=st.columns(4)

with f1:
    meses=sorted([x for x in df["_mes"].dropna().unique() if x!="NaT"])
    sel_mes=st.multiselect("Mes",meses,default=meses)
with f2:
    sedes=sorted(df["_sede"].unique())
    sel_sede=st.multiselect("Sede / Almacén",sedes,default=sedes)
with f3:
    estados=sorted(df["_estado"].unique())
    sel_estado=st.multiselect("Estado",estados,default=estados)
with f4:
    encargados=sorted(df["_encargado"].unique())
    sel_enc=st.multiselect("Encargado / Supervisor",encargados,default=encargados)

work=df.copy()
if sel_mes: work=work[work["_mes"].isin(sel_mes)]
if sel_sede: work=work[work["_sede"].isin(sel_sede)]
if sel_estado: work=work[work["_estado"].isin(sel_estado)]
if sel_enc: work=work[work["_encargado"].isin(sel_enc)]

st.markdown('</div>', unsafe_allow_html=True)

# -----------------------------
# KPIs principales
# -----------------------------
total=work["_guia"].nunique()
sedes_n=work["_sede"].nunique()
estados_n=work["_estado"].nunique()
enc_n=work["_encargado"].nunique()

a,b,c1,d=st.columns(4)
kpi("📄 TOTAL DE GUÍAS",fmt(total),"Guías únicas")
kpi("🏢 SEDES",fmt(sedes_n),"Sedes con movimiento")
kpi("📌 ESTADOS",fmt(estados_n),"Estados registrados")
kpi("👤 ENCARGADOS",fmt(enc_n),"Encargados / supervisores")

# -----------------------------
# Comparación
# -----------------------------
if len(datasets)>=2:
    old_name,old_df,old_c=datasets[0]
    old_f=old_df.copy()
    new_f=df.copy()

    old_n=old_f["_guia"].nunique()
    new_n=new_f["_guia"].nunique()
    dif=new_n-old_n
    var=None if old_n==0 else dif/old_n*100

    st.subheader("🔄 Variación contra la carga anterior")
    x1,x2,x3,x4=st.columns(4)
    kpi("Anterior",fmt(old_n),old_name)
    kpi("Actual",fmt(new_n),actual_name)
    signo="🟢 ↑ Aumentó" if dif>0 else ("🔴 ↓ Disminuyó" if dif<0 else "⚪ Sin cambio")
    kpi("Diferencia",f"{dif:+,}".replace(",","."),signo)
    kpi("Variación", "N/D" if var is None else f"{var:+.2f}%", "vs. carga anterior")

# -----------------------------
# Evolución mensual
# -----------------------------
st.subheader("📈 Evolución mensual de guías")

if c["fecha"]:
    mensual=(
        work.dropna(subset=["_fecha"])
        .groupby("_mes")["_guia"].nunique()
        .sort_index()
        .reset_index(name="Guías")
    )
    if not mensual.empty:
        st.bar_chart(mensual.set_index("_mes")["Guías"])
        st.dataframe(mensual,use_container_width=True,hide_index=True)
else:
    st.warning("No se encontró fecha. La evolución mensual no puede calcularse.")

# -----------------------------
# Matriz Sede x Mes
# -----------------------------
st.subheader("🏢 Matriz de Guías por Sede y Mes")

if c["fecha"]:
    matriz=work.pivot_table(
        index="_sede",
        columns="_mes",
        values="_guia",
        aggfunc=pd.Series.nunique,
        fill_value=0
    )
    matriz["Total general"]=matriz.sum(axis=1)
    matriz=matriz.sort_values("Total general",ascending=False)

    total_row=matriz.sum(axis=0).to_frame().T
    total_row.index=["Total general"]
    matriz=pd.concat([matriz,total_row])

    st.dataframe(
        matriz.style.format("{:,.0f}"),
        use_container_width=True,
        height=500
    )
else:
    matriz=work.groupby("_sede")["_guia"].nunique().sort_values(ascending=False).to_frame("Guías")
    st.dataframe(matriz,use_container_width=True)

# -----------------------------
# Estado por sede
# -----------------------------
st.subheader("📌 Estado de las guías")

tab1,tab2,tab3=st.tabs(["Estado general","Estado por sede","Encargados"])

with tab1:
    estado=(
        work.groupby("_estado")["_guia"].nunique()
        .sort_values(ascending=False)
        .reset_index(name="Guías")
    )
    estado["%"]=(estado["Guías"]/max(total,1)*100).round(2)
    st.dataframe(estado,use_container_width=True,hide_index=True)

with tab2:
    est_sede=work.pivot_table(
        index="_sede",
        columns="_estado",
        values="_guia",
        aggfunc=pd.Series.nunique,
        fill_value=0
    )
    est_sede["Total"]=est_sede.sum(axis=1)
    est_sede=est_sede.sort_values("Total",ascending=False)
    st.dataframe(est_sede.style.format("{:,.0f}"),use_container_width=True)

with tab3:
    enc=(
        work.groupby("_encargado")["_guia"].nunique()
        .sort_values(ascending=False)
        .reset_index(name="Guías")
    )
    enc["% del total"]=(enc["Guías"]/max(total,1)*100).round(2)
    st.dataframe(enc,use_container_width=True,hide_index=True)

# -----------------------------
# Matriz Sede + Encargado
# -----------------------------
st.subheader("👤 Encargados por Sede")

mat_enc=work.pivot_table(
    index="_encargado",
    columns="_sede",
    values="_guia",
    aggfunc=pd.Series.nunique,
    fill_value=0,
    margins=True,
    margins_name="Total general"
)
mat_enc=mat_enc.sort_values("Total general",ascending=False)
st.dataframe(mat_enc.style.format("{:,.0f}"),use_container_width=True,height=450)

# -----------------------------
# Detalle de guías
# -----------------------------
st.subheader("📄 Detalle de guías")

cols_to_show=["_guia"]
rename={"_guia":"Guía"}

if c["fecha"]:
    cols_to_show.append("_fecha"); rename["_fecha"]="Fecha"
cols_to_show += ["_sede","_estado","_encargado"]
rename.update({
    "_sede":"Sede",
    "_estado":"Estado",
    "_encargado":"Encargado"
})

detalle=work[cols_to_show].drop_duplicates(subset=["_guia"]).rename(columns=rename)
st.dataframe(detalle,use_container_width=True,height=500,hide_index=True)

# -----------------------------
# Columnas detectadas
# -----------------------------
with st.expander("ℹ️ Columnas utilizadas"):
    st.write({
        "Guía": c["guia"],
        "Fecha": c["fecha"],
        "Estado": c["estado"],
        "Sede": c["sede"],
        "Encargado": c["encargado"]
    })

st.caption("Este dashboard analiza únicamente GUÍAS, ESTADO, SEDE y ENCARGADOS. No utiliza materiales.")
