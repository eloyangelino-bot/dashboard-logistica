
import io
import pandas as pd
import numpy as np
import streamlit as st

st.set_page_config(
    page_title="Matriz de Guías por Sede",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------
# ESTILO
# -----------------------------
st.markdown("""
<style>
    .main .block-container {padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1500px;}
    h1 {font-size: 2rem !important; margin-bottom: .15rem !important;}
    .subtitle {color:#64748b; margin-bottom:1rem;}
    .kpi {
        border:1px solid #e2e8f0; border-radius:12px; padding:15px 18px;
        background:white; min-height:92px; box-shadow:0 1px 3px rgba(15,23,42,.05);
    }
    .kpi-blue {border-left:5px solid #2563eb;}
    .kpi-green {border-left:5px solid #16a34a;}
    .kpi-orange {border-left:5px solid #f59e0b;}
    .kpi-purple {border-left:5px solid #7c3aed;}
    .kpi-label {font-size:.78rem; color:#64748b; font-weight:700; text-transform:uppercase;}
    .kpi-value {font-size:1.65rem; font-weight:800; color:#0f172a; margin-top:5px;}
    .section-title {font-size:1.05rem; font-weight:800; color:#0f172a; margin:.4rem 0 .7rem;}
    .note {font-size:.78rem; color:#64748b;}
    [data-testid="stDataFrame"] {border-radius:10px;}
</style>
""", unsafe_allow_html=True)


# -----------------------------
# UTILIDADES
# -----------------------------
REQUIRED = ["P. Emis", "Número", "F.Almac."]

def normalize_col(c):
    return " ".join(str(c).replace("\n", " ").split()).strip()

def clean_text(s):
    return (
        s.astype("string")
        .fillna("")
        .str.strip()
        .replace({"nan": "", "None": "", "<NA>": ""})
    )

def clean_id(s):
    s = clean_text(s)
    # Evita claves tipo 123.0 cuando Excel convirtió un identificador entero a float.
    s = s.str.replace(r"^(-?\d+)\.0$", r"\1", regex=True)
    return s

def find_col(df, wanted):
    wanted_norm = normalize_col(wanted).lower()
    cols = {normalize_col(c).lower(): c for c in df.columns}
    if wanted_norm in cols:
        return cols[wanted_norm]
    # Coincidencia tolerante
    for c in df.columns:
        if normalize_col(c).lower().replace(" ", "") == wanted_norm.replace(" ", ""):
            return c
    return None

def read_uploaded(uploaded):
    data = uploaded.getvalue()
    name = uploaded.name.lower()

    if name.endswith(".csv"):
        try:
            df = pd.read_csv(io.BytesIO(data), sep=None, engine="python")
        except Exception:
            df = pd.read_csv(io.BytesIO(data))
    else:
        xls = pd.ExcelFile(io.BytesIO(data))
        best_sheet = None
        best_rows = -1
        for sheet in xls.sheet_names:
            try:
                tmp = pd.read_excel(io.BytesIO(data), sheet_name=sheet)
                score = len(tmp.dropna(how="all"))
                if score > best_rows:
                    best_rows = score
                    best_sheet = sheet
            except Exception:
                pass
        if best_sheet is None:
            raise ValueError("No se pudo leer ninguna hoja del Excel.")
        df = pd.read_excel(io.BytesIO(data), sheet_name=best_sheet)

    df.columns = [normalize_col(c) for c in df.columns]
    return df

def build_guide_level(df):
    """
    Regla central:
    una guía única = P. Emis + Número.

    El Excel puede tener muchas filas por una misma guía porque
    una guía puede contener muchos materiales. Aquí se colapsan
    esas filas a una sola fila por guía.
    """
    mapping = {}
    for wanted in [
        "P. Emis", "Número", "F.Almac.", "Estado",
        "Doc . Encargado", "Encargado", "C. Alm", "Almacen"
    ]:
        mapping[wanted] = find_col(df, wanted)

    missing = [x for x in REQUIRED if mapping[x] is None]
    if missing:
        raise ValueError(
            "Faltan columnas obligatorias para identificar una guía: "
            + ", ".join(missing)
        )

    work = pd.DataFrame(index=df.index)
    work["_emis"] = clean_id(df[mapping["P. Emis"]])
    work["_numero"] = clean_id(df[mapping["Número"]])

    # No se permite convertir filas incompletas en guías.
    work["_guia"] = np.where(
        (work["_emis"] != "") & (work["_numero"] != ""),
        work["_emis"] + " | " + work["_numero"],
        ""
    )

    fecha = pd.to_datetime(df[mapping["F.Almac."]], errors="coerce", dayfirst=True)
    work["_fecha"] = fecha

    for out, wanted in [
        ("_estado", "Estado"),
        ("_doc_encargado", "Doc . Encargado"),
        ("_encargado", "Encargado"),
        ("_c_alm", "C. Alm"),
        ("_almacen", "Almacen"),
    ]:
        col = mapping[wanted]
        if col is None:
            work[out] = "SIN DATO"
        else:
            work[out] = clean_text(df[col]).replace("", "SIN DATO")

    valid = work[work["_guia"] != ""].copy()

    # Agrupación a nivel guía. Cada guía cuenta una sola vez.
    def first_nonblank(series):
        s = clean_text(series).replace("SIN DATO", "")
        s = s[s != ""]
        return s.iloc[0] if len(s) else "SIN DATO"

    def combine_values(series):
        vals = sorted(set(clean_text(series).replace("", "SIN DATO")))
        vals = [v for v in vals if v != "SIN DATO"]
        if not vals:
            return "SIN DATO"
        if len(vals) == 1:
            return vals[0]
        return "MÚLTIPLES: " + " / ".join(vals[:5])

    agg = (
        valid.groupby("_guia", sort=False)
        .agg(
            _emis=("_emis", first_nonblank),
            _numero=("_numero", first_nonblank),
            _fecha=("_fecha", lambda s: s.dropna().min() if s.notna().any() else pd.NaT),
            _estado=("_estado", combine_values),
            _doc_encargado=("_doc_encargado", combine_values),
            _encargado=("_encargado", combine_values),
            _c_alm=("_c_alm", combine_values),
            _almacen=("_almacen", combine_values),
        )
        .reset_index()
    )

    agg["_mes"] = agg["_fecha"].dt.to_period("M").astype("string")
    agg.loc[agg["_fecha"].isna(), "_mes"] = "SIN FECHA"
    return agg

def pct_change(current, previous):
    if previous == 0:
        return None if current == 0 else np.inf
    return (current - previous) / previous * 100

def fmt_pct(v):
    if v is None:
        return "—"
    if np.isinf(v):
        return "NUEVO"
    return f"{v:+.1f}%"

def make_matrix(df):
    if df.empty:
        return pd.DataFrame()
    d = df.copy()
    d["_almacen"] = clean_text(d["_almacen"])
    d["_mes"] = clean_text(d["_mes"])
    matrix = pd.pivot_table(
        d,
        index="_almacen",
        columns="_mes",
        values="_guia",
        aggfunc="nunique",
        fill_value=0,
    )
    # Orden cronológico; SIN FECHA al final.
    months = [c for c in matrix.columns if c != "SIN FECHA"]
    months = sorted(months)
    cols = months + (["SIN FECHA"] if "SIN FECHA" in matrix.columns else [])
    matrix = matrix.reindex(columns=cols, fill_value=0)
    matrix["Total general"] = matrix.sum(axis=1)
    total = matrix.sum(axis=0).to_frame().T
    total.index = ["Total general"]
    return pd.concat([matrix, total])

def style_matrix(df):
    if df.empty:
        return df
    return df.style.format("{:,.0f}").set_properties(**{"text-align": "center"})

def monthly_series(df):
    if df.empty:
        return pd.DataFrame(columns=["Mes", "Guías"])
    x = (
        df[df["_mes"] != "SIN FECHA"]
        .groupby("_mes")["_guia"]
        .nunique()
        .sort_index()
        .rename("Guías")
        .reset_index()
        .rename(columns={"_mes": "Mes"})
    )
    return x

# -----------------------------
# CARGA
# -----------------------------
st.title("Matriz Completa de Operaciones por Sede")
st.markdown(
    '<div class="subtitle">Consolidado de guías únicas. '
    '<b>1 guía = P. Emis + Número</b>; los materiales no se cuentan como guías.</div>',
    unsafe_allow_html=True
)

with st.sidebar:
    st.header("📂 Archivos")
    actual_file = st.file_uploader(
        "Carga actual",
        type=["xlsx", "xls", "csv"],
        key="actual"
    )
    anterior_file = st.file_uploader(
        "Carga anterior (opcional)",
        type=["xlsx", "xls", "csv"],
        key="anterior"
    )
    st.divider()
    st.caption("Columnas obligatorias:")
    st.code("P. Emis\nNúmero\nF.Almac.", language="text")
    st.caption("La matriz, estados, sedes y encargados se calculan a nivel de guía única.")

if not actual_file:
    st.info("Carga el archivo actual desde la barra lateral para generar la matriz.")
    st.stop()

try:
    raw_actual = read_uploaded(actual_file)
    actual = build_guide_level(raw_actual)
except Exception as e:
    st.error(f"No se pudo procesar la carga actual: {e}")
    st.stop()

anterior = None
if anterior_file:
    try:
        raw_anterior = read_uploaded(anterior_file)
        anterior = build_guide_level(raw_anterior)
    except Exception as e:
        st.warning(f"La carga anterior no pudo procesarse: {e}")

# -----------------------------
# FILTROS
# -----------------------------
st.sidebar.divider()
st.sidebar.header("🔎 Filtros")

def options(df, col):
    vals = sorted(df[col].dropna().astype(str).unique().tolist())
    return vals

fechas = actual["_fecha"].dropna()
if len(fechas):
    min_date, max_date = fechas.min().date(), fechas.max().date()
    date_value = st.sidebar.date_input(
        "Fecha de almacén",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )
else:
    date_value = None

sede_opts = options(actual, "_almacen")
estado_opts = options(actual, "_estado")
enc_opts = options(actual, "_encargado")

sedes = st.sidebar.multiselect("Sede / Almacén", sede_opts)
estados = st.sidebar.multiselect("Estado", estado_opts)
encargados = st.sidebar.multiselect("Encargado", enc_opts)

df = actual.copy()

if date_value and len(date_value) == 2:
    ini, fin = pd.Timestamp(date_value[0]), pd.Timestamp(date_value[1]) + pd.Timedelta(days=1)
    df = df[(df["_fecha"] >= ini) & (df["_fecha"] < fin)]

if sedes:
    df = df[df["_almacen"].isin(sedes)]
if estados:
    df = df[df["_estado"].isin(estados)]
if encargados:
    df = df[df["_encargado"].isin(encargados)]

# -----------------------------
# KPIs
# -----------------------------
total = df["_guia"].nunique()

sede_counts = df.groupby("_almacen")["_guia"].nunique().sort_values(ascending=False)
top_sede = sede_counts.index[0] if len(sede_counts) else "—"
top_sede_n = int(sede_counts.iloc[0]) if len(sede_counts) else 0

m = monthly_series(df)
if len(m):
    peak_row = m.loc[m["Guías"].idxmax()]
    peak_month = peak_row["Mes"]
    peak_n = int(peak_row["Guías"])
else:
    peak_month, peak_n = "—", 0

states = df.groupby("_estado")["_guia"].nunique().sort_values(ascending=False)
top_state = states.index[0] if len(states) else "—"
top_state_n = int(states.iloc[0]) if len(states) else 0

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(f'<div class="kpi kpi-blue"><div class="kpi-label">Total general</div><div class="kpi-value">{total:,.0f}</div></div>', unsafe_allow_html=True)
with c2:
    st.markdown(f'<div class="kpi kpi-green"><div class="kpi-label">Top sede</div><div class="kpi-value">{top_sede_n:,.0f}</div><div class="note">{top_sede}</div></div>', unsafe_allow_html=True)
with c3:
    st.markdown(f'<div class="kpi kpi-orange"><div class="kpi-label">Pico del mes</div><div class="kpi-value">{peak_n:,.0f}</div><div class="note">{peak_month}</div></div>', unsafe_allow_html=True)
with c4:
    st.markdown(f'<div class="kpi kpi-purple"><div class="kpi-label">Estado principal</div><div class="kpi-value">{top_state_n:,.0f}</div><div class="note">{top_state}</div></div>', unsafe_allow_html=True)

st.write("")

# -----------------------------
# BLOQUE PRINCIPAL: EVOLUCIÓN + MATRIZ
# -----------------------------
left, right = st.columns([0.28, 0.72], gap="large")

with left:
    st.markdown('<div class="section-title">📈 Evolución Mensual</div>', unsafe_allow_html=True)
    if len(m):
        maxv = max(int(m["Guías"].max()), 1)
        for _, row in m.iterrows():
            mes = str(row["Mes"])
            val = int(row["Guías"])
            st.markdown(
                f"""
                <div style="display:flex;align-items:center;gap:8px;margin:8px 0;">
                    <div style="width:32px;font-size:.82rem;color:#475569;">{mes[-2:]}</div>
                    <div style="flex:1;background:#e5eaf1;height:12px;border-radius:4px;overflow:hidden;">
                        <div style="width:{val/maxv*100:.1f}%;background:#2563eb;height:12px;border-radius:4px;"></div>
                    </div>
                    <div style="width:60px;text-align:right;font-weight:700;font-size:.82rem;">{val:,.0f}</div>
                </div>
                """,
                unsafe_allow_html=True
            )
    else:
        st.info("Sin fechas para mostrar.")

    st.markdown('<div class="section-title" style="margin-top:22px;">📊 Resumen de Bloques</div>', unsafe_allow_html=True)
    if len(sede_counts):
        total_sede = sede_counts.sum()
        for sede, val in sede_counts.head(8).items():
            pct = val / total_sede * 100 if total_sede else 0
            st.markdown(
                f'<div style="display:flex;justify-content:space-between;border-bottom:1px solid #eef2f7;padding:7px 2px;font-size:.82rem;">'
                f'<span>{sede}</span><b>{int(val):,} ({pct:.1f}%)</b></div>',
                unsafe_allow_html=True
            )
    else:
        st.info("Sin datos.")

with right:
    st.markdown('<div class="section-title">📋 Matriz Sede × Mes — Guías Únicas</div>', unsafe_allow_html=True)
    matrix = make_matrix(df)
    if matrix.empty:
        st.info("No hay datos con los filtros seleccionados.")
    else:
        st.dataframe(
            style_matrix(matrix),
            use_container_width=True,
            height=600,
        )

st.caption("Cada celda representa cantidad de guías únicas. Una guía repetida por múltiples materiales se contabiliza una sola vez.")

# -----------------------------
# DETALLE
# -----------------------------
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Estado", "Encargados", "Comparación", "Guías nuevas / desaparecidas", "Detalle de guías"
])

with tab1:
    st.subheader("Guías únicas por Estado")
    state_tbl = (
        df.groupby("_estado")["_guia"].nunique()
        .sort_values(ascending=False)
        .rename("Guías únicas")
        .to_frame()
    )
    if len(state_tbl):
        state_tbl["%"] = state_tbl["Guías únicas"] / total * 100
        state_tbl["%"] = state_tbl["%"].round(1)
        st.dataframe(state_tbl, use_container_width=True)
    else:
        st.info("Sin datos.")

    st.subheader("Estado × Sede")
    p = pd.pivot_table(
        df, index="_almacen", columns="_estado",
        values="_guia", aggfunc="nunique", fill_value=0
    )
    if len(p):
        p["Total"] = p.sum(axis=1)
        st.dataframe(p.style.format("{:,.0f}"), use_container_width=True)
    else:
        st.info("Sin datos.")

with tab2:
    st.subheader("Guías únicas por Encargado")
    enc_tbl = (
        df.groupby("_encargado")["_guia"].nunique()
        .sort_values(ascending=False)
        .rename("Guías únicas")
        .to_frame()
    )
    if len(enc_tbl):
        enc_tbl["%"] = (enc_tbl["Guías únicas"] / total * 100).round(1)
        st.dataframe(enc_tbl, use_container_width=True)

    st.subheader("Encargado × Sede")
    p2 = pd.pivot_table(
        df, index="_encargado", columns="_almacen",
        values="_guia", aggfunc="nunique", fill_value=0
    )
    if len(p2):
        p2["Total"] = p2.sum(axis=1)
        st.dataframe(p2.style.format("{:,.0f}"), use_container_width=True)
    else:
        st.info("Sin datos.")

with tab3:
    st.subheader("Comparación de carga anterior vs actual")
    if anterior is None:
        st.info("Carga un archivo anterior para activar la comparación.")
    else:
        old_keys = set(anterior["_guia"])
        new_keys = set(actual["_guia"])

        old_n = len(old_keys)
        new_n = len(new_keys)
        nuevas = new_keys - old_keys
        desaparecidas = old_keys - new_keys
        permanecen = old_keys & new_keys
        diff = new_n - old_n
        pct = pct_change(new_n, old_n)

        a, b, c, d = st.columns(4)
        a.metric("Carga anterior", f"{old_n:,}")
        b.metric("Carga actual", f"{new_n:,}", delta=f"{diff:+,}")
        c.metric("Nuevas guías", f"{len(nuevas):,}")
        d.metric("Desaparecidas", f"{len(desaparecidas):,}")

        st.write(f"**Variación:** {fmt_pct(pct)} · **Permanecen:** {len(permanecen):,}")

        comp = pd.DataFrame({
            "Indicador": ["Guías anteriores", "Guías actuales", "Diferencia", "Variación %", "Nuevas", "Desaparecidas", "Permanecen"],
            "Valor": [old_n, new_n, diff, fmt_pct(pct), len(nuevas), len(desaparecidas), len(permanecen)]
        })
        st.dataframe(comp, use_container_width=True, hide_index=True)

        st.subheader("Comparación por sede")
        old_s = anterior.groupby("_almacen")["_guia"].nunique().rename("Anterior")
        new_s = actual.groupby("_almacen")["_guia"].nunique().rename("Actual")
        cs = pd.concat([old_s, new_s], axis=1).fillna(0)
        cs["Diferencia"] = cs["Actual"] - cs["Anterior"]
        cs["Variación %"] = np.where(
            cs["Anterior"] == 0,
            np.where(cs["Actual"] == 0, 0, np.inf),
            (cs["Actual"] - cs["Anterior"]) / cs["Anterior"] * 100
        )
        cs = cs.sort_values("Actual", ascending=False)
        st.dataframe(
            cs.style.format({
                "Anterior": "{:,.0f}",
                "Actual": "{:,.0f}",
                "Diferencia": "{:+,.0f}",
                "Variación %": lambda x: "NUEVO" if np.isinf(x) else f"{x:+.1f}%"
            }),
            use_container_width=True
        )

with tab4:
    if anterior is None:
        st.info("Carga un archivo anterior para identificar guías nuevas y desaparecidas.")
    else:
        old_keys = set(anterior["_guia"])
        new_keys = set(actual["_guia"])
        nuevas = new_keys - old_keys
        desaparecidas = old_keys - new_keys

        new_detail = actual[actual["_guia"].isin(nuevas)].copy()
        old_detail = anterior[anterior["_guia"].isin(desaparecidas)].copy()

        st.subheader(f"🟢 Guías nuevas ({len(nuevas):,})")
        cols = ["_guia", "_fecha", "_almacen", "_estado", "_encargado"]
        st.dataframe(
            new_detail[cols].rename(columns={
                "_guia":"Guía","_fecha":"Fecha","_almacen":"Almacen",
                "_estado":"Estado","_encargado":"Encargado"
            }).sort_values("Fecha", na_position="last"),
            use_container_width=True, hide_index=True
        )

        st.subheader(f"🔴 Guías desaparecidas ({len(desaparecidas):,})")
        st.dataframe(
            old_detail[cols].rename(columns={
                "_guia":"Guía","_fecha":"Fecha","_almacen":"Almacen",
                "_estado":"Estado","_encargado":"Encargado"
            }).sort_values("Fecha", na_position="last"),
            use_container_width=True, hide_index=True
        )

with tab5:
    st.subheader(f"Detalle de guías únicas ({len(df):,})")
    detail = df.rename(columns={
        "_guia":"Guía única",
        "_emis":"P. Emis",
        "_numero":"Número",
        "_fecha":"F.Almac.",
        "_estado":"Estado",
        "_doc_encargado":"Doc . Encargado",
        "_encargado":"Encargado",
        "_c_alm":"C. Alm",
        "_almacen":"Almacen",
        "_mes":"Mes",
    })[
        ["Guía única","P. Emis","Número","F.Almac.","Estado",
         "Doc . Encargado","Encargado","C. Alm","Almacen","Mes"]
    ].sort_values("F.Almac.", na_position="last")

    st.dataframe(detail, use_container_width=True, height=650, hide_index=True)

    csv = detail.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "⬇️ Descargar detalle de guías únicas (CSV)",
        csv,
        "guias_unicas.csv",
        "text/csv"
    )
