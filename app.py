import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="Dashboard Logística", page_icon="📊", layout="wide")

# ============================================================
# UTILIDADES
# ============================================================

def norm(x):
    s = str(x).strip().lower()
    repl = {
        "á":"a","é":"e","í":"i","ó":"o","ú":"u","ñ":"n",
        "_":" ","-":" "
    }
    for a, b in repl.items():
        s = s.replace(a, b)
    return " ".join(s.split())

def find_col(df, candidates):
    cols = list(df.columns)
    nc = {c: norm(c) for c in cols}

    # exacto
    for cand in candidates:
        c = norm(cand)
        for col in cols:
            if nc[col] == c:
                return col

    # parcial
    for cand in candidates:
        c = norm(cand)
        for col in cols:
            if c and c in nc[col]:
                return col
    return None

def find_cols(df):
    return {
        "guia": find_col(df, [
            "key", "guia", "nro guia", "numero guia", "número de guía",
            "guia de remision", "guía de remisión", "documento"
        ]),
        "fecha": find_col(df, [
            "fecha", "fecha salida", "fecha despacho", "fecha de salida",
            "fecha entrega", "created at", "timestamp"
        ]),
        "supervisor": find_col(df, [
            "supervisor", "responsable", "encargado", "solicitante"
        ]),
        "almacen": find_col(df, [
            "almacen", "almacén", "almacen destino", "centro", "codigo almacen"
        ]),
        "material": find_col(df, [
            "material", "codigo material", "codigo", "cod material",
            "item", "ítem", "producto", "descripcion", "descripción"
        ]),
        "descripcion": find_col(df, [
            "descripcion", "descripción", "nombre material", "producto"
        ]),
        "cantidad": find_col(df, [
            "cantidad", "cant", "cantidad salida", "cantidad entregada",
            "unidades", "qty"
        ]),
        "estado": find_col(df, [
            "estado", "estatus", "status", "aprobacion", "aprobación"
        ]),
        "familia": find_col(df, [
            "familia", "categoria", "categoría", "grupo", "tipo material"
        ]),
        "costo": find_col(df, [
            "costo", "costo unitario", "precio", "valor", "importe", "total"
        ])
    }

def to_num(v):
    if pd.isna(v) or str(v).strip() == "":
        return 0.0
    s = str(v).strip().replace("S/", "").replace("$", "").replace(" ", "")
    # soporta 1.234,56 y 1234.56
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except:
        return 0.0

def unique_count(df, col):
    if not col:
        return None
    s = df[col].astype(str).str.strip()
    s = s[(s != "") & (s.str.lower() != "nan")]
    return int(s.nunique())

def read_excel(uploaded):
    if uploaded.name.lower().endswith(".csv"):
        return pd.read_csv(uploaded), "CSV"
    xls = pd.ExcelFile(uploaded)
    # Elegimos la hoja con más filas útiles
    best_sheet = None
    best_rows = -1
    for sheet in xls.sheet_names:
        try:
            tmp = pd.read_excel(uploaded, sheet_name=sheet)
            score = len(tmp.dropna(how="all"))
            if score > best_rows:
                best_rows = score
                best_sheet = sheet
        except:
            pass
    df = pd.read_excel(uploaded, sheet_name=best_sheet)
    return df, best_sheet

def analyze(df):
    cols = find_cols(df)

    guia = unique_count(df, cols["guia"])
    registros = len(df)

    # Si existe KEY/guía, se usa para guías. Nunca se confunde con cantidad de filas.
    total_guias = guia if guia is not None else None

    if cols["cantidad"]:
        unidades = df[cols["cantidad"]].apply(to_num).sum()
    else:
        unidades = None

    aprobadas = pendientes = None
    if cols["estado"]:
        estado = df[cols["estado"]].astype(str).map(norm)
        aprobadas = int(estado.str.contains("aprob", na=False).sum())
        pendientes = int(
            (estado.str.contains("pend", na=False) |
             estado.str.contains("proceso", na=False) |
             estado.str.contains("en espera", na=False)).sum()
        )

    materiales = unique_count(df, cols["material"])
    supervisores = unique_count(df, cols["supervisor"])
    almacenes = unique_count(df, cols["almacen"])

    return {
        "registros": registros,
        "guias": total_guias,
        "unidades": unidades,
        "aprobadas": aprobadas,
        "pendientes": pendientes,
        "materiales": materiales,
        "supervisores": supervisores,
        "almacenes": almacenes,
        "cols": cols
    }

def fmt(v):
    if v is None:
        return "—"
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def delta(old, new):
    if old is None or new is None:
        return None, None
    d = new - old
    p = None if old == 0 and new != 0 else (0 if old == 0 else d / old * 100)
    return d, p

def kpi(col, title, value, old=None):
    if value is None:
        col.metric(title, "—")
        return
    if old is None:
        col.metric(title, fmt(value))
    else:
        d, p = delta(old, value)
        if d is None:
            col.metric(title, fmt(value))
        else:
            txt = f"{d:+,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            if p is not None:
                txt += f" ({p:+.2f}%)"
            col.metric(title, fmt(value), txt)

def comparison_rows(old_a, new_a):
    items = [
        ("Registros", "registros"),
        ("Guías", "guias"),
        ("Unidades", "unidades"),
        ("Guías aprobadas", "aprobadas"),
        ("Guías pendientes", "pendientes"),
        ("Materiales", "materiales"),
        ("Supervisores", "supervisores"),
        ("Almacenes", "almacenes"),
    ]
    rows = []
    for label, key in items:
        old, new = old_a.get(key), new_a.get(key)
        d, p = delta(old, new)
        if d is None:
            trend = "Sin dato"
        elif d > 0:
            trend = "🟢 ↑ Aumenta"
        elif d < 0:
            trend = "🔴 ↓ Disminuye"
        else:
            trend = "⚪ → Sin cambio"
        rows.append({
            "Indicador": label,
            "Anterior": fmt(old),
            "Actual": fmt(new),
            "Diferencia": "—" if d is None else f"{d:+,.2f}",
            "Variación %": "N/D" if p is None else f"{p:+.2f}%",
            "Tendencia": trend
        })
    return pd.DataFrame(rows)

def group_analysis(df, cols, group_key, value_label="Unidades"):
    c = cols.get(group_key)
    if not c:
        return None
    temp = df.copy()
    temp[c] = temp[c].astype(str).str.strip()
    temp = temp[temp[c] != ""]
    if cols["cantidad"]:
        temp["_valor"] = temp[cols["cantidad"]].apply(to_num)
        out = temp.groupby(c, dropna=False)["_valor"].sum().reset_index()
        out.columns = [c, value_label]
    else:
        out = temp.groupby(c, dropna=False).size().reset_index(name="Registros")
    return out.sort_values(out.columns[-1], ascending=False)

# ============================================================
# INTERFAZ
# ============================================================

st.title("📊 Dashboard Logística")
st.caption(
    "Analiza la carga actual y, cuando se cargan dos archivos, compara automáticamente "
    "la carga actual contra la anterior."
)

uploads = st.file_uploader(
    "📂 Cargar archivo(s) Excel",
    type=["xlsx", "xls", "csv"],
    accept_multiple_files=True
)

if not uploads:
    st.info(
        "Carga el Excel de salidas. Para comparar cambios, carga 2 archivos: "
        "primero el anterior y después el actual."
    )
    st.stop()

data = []
for up in uploads[:2]:
    try:
        df, hoja = read_excel(up)
        data.append({
            "name": up.name,
            "sheet": hoja,
            "df": df,
            "analysis": analyze(df)
        })
    except Exception as e:
        st.error(f"No se pudo leer {up.name}: {e}")

if not data:
    st.stop()

# ============================================================
# CARGA ACTUAL
# ============================================================

if len(data) == 1:
    current = data[0]
    a = current["analysis"]

    st.success(
        f"Carga actual: **{current['name']}** · "
        f"{a['registros']:,} registros".replace(",", ".")
    )

    c1, c2, c3, c4 = st.columns(4)
    kpi(c1, "📄 Guías", a["guias"])
    kpi(c2, "📦 Unidades", a["unidades"])
    kpi(c3, "🧰 Materiales", a["materiales"])
    kpi(c4, "👤 Supervisores", a["supervisores"])

    st.subheader("🔎 ¿Qué encontró el sistema?")

    detected = pd.DataFrame([
        {"Dato": "Guía / KEY", "Columna detectada": a["cols"]["guia"] or "No encontrada"},
        {"Dato": "Fecha", "Columna detectada": a["cols"]["fecha"] or "No encontrada"},
        {"Dato": "Supervisor", "Columna detectada": a["cols"]["supervisor"] or "No encontrada"},
        {"Dato": "Almacén", "Columna detectada": a["cols"]["almacen"] or "No encontrada"},
        {"Dato": "Material", "Columna detectada": a["cols"]["material"] or "No encontrada"},
        {"Dato": "Cantidad", "Columna detectada": a["cols"]["cantidad"] or "No encontrada"},
        {"Dato": "Estado", "Columna detectada": a["cols"]["estado"] or "No encontrada"},
    ])
    st.dataframe(detected, use_container_width=True, hide_index=True)

    # Análisis por dimensiones
    st.subheader("📊 Análisis de la carga actual")

    tabs = st.tabs(["Supervisores", "Materiales", "Almacenes", "Estados", "Mensual"])

    with tabs[0]:
        table = group_analysis(current["df"], a["cols"], "supervisor")
        if table is None:
            st.warning("No se encontró una columna de supervisor.")
        else:
            st.dataframe(table.head(30), use_container_width=True, hide_index=True)

    with tabs[1]:
        table = group_analysis(current["df"], a["cols"], "material")
        if table is None:
            st.warning("No se encontró una columna de material.")
        else:
            st.dataframe(table.head(50), use_container_width=True, hide_index=True)

    with tabs[2]:
        table = group_analysis(current["df"], a["cols"], "almacen")
        if table is None:
            st.warning("No se encontró una columna de almacén.")
        else:
            st.dataframe(table.head(30), use_container_width=True, hide_index=True)

    with tabs[3]:
        estado = a["cols"]["estado"]
        if not estado:
            st.warning(
                "El archivo no tiene Estado por línea. Por eso el sistema NO inventa "
                "cuántas guías están aprobadas."
            )
        else:
            st.dataframe(
                current["df"][estado].astype(str).value_counts().reset_index(
                    name="Registros"
                ).rename(columns={"index": "Estado"}),
                use_container_width=True,
                hide_index=True
            )

    with tabs[4]:
        fecha = a["cols"]["fecha"]
        if not fecha:
            st.warning("No se encontró una columna de fecha.")
        else:
            tmp = current["df"].copy()
            tmp["_fecha"] = pd.to_datetime(tmp[fecha], errors="coerce", dayfirst=True)
            tmp = tmp.dropna(subset=["_fecha"])
            if tmp.empty:
                st.warning("La columna encontrada no contiene fechas reconocibles.")
            else:
                tmp["Mes"] = tmp["_fecha"].dt.to_period("M").astype(str)
                if a["cols"]["cantidad"]:
                    tmp["_cantidad"] = tmp[a["cols"]["cantidad"]].apply(to_num)
                    monthly = tmp.groupby("Mes")["_cantidad"].sum().reset_index()
                    monthly.columns = ["Mes", "Unidades"]
                else:
                    monthly = tmp.groupby("Mes").size().reset_index(name="Registros")
                st.dataframe(monthly, use_container_width=True, hide_index=True)

    st.subheader("📋 Registros originales")
    st.dataframe(current["df"].head(200), use_container_width=True, hide_index=True)

# ============================================================
# COMPARACIÓN
# ============================================================

else:
    previous = data[0]
    current = data[1]

    old_a = previous["analysis"]
    new_a = current["analysis"]

    st.success(
        f"**Actual:** {current['name']}  |  **Anterior:** {previous['name']}"
    )

    st.subheader("📈 Indicadores: actual vs. anterior")

    c1, c2, c3, c4 = st.columns(4)
    kpi(c1, "📄 Guías", new_a["guias"], old_a["guias"])
    kpi(c2, "📦 Unidades", new_a["unidades"], old_a["unidades"])
    kpi(c3, "🧰 Materiales", new_a["materiales"], old_a["materiales"])
    kpi(c4, "👤 Supervisores", new_a["supervisores"], old_a["supervisores"])

    st.dataframe(
        comparison_rows(old_a, new_a),
        use_container_width=True,
        hide_index=True
    )

    st.subheader("🔎 Control de calidad de la lectura")

    checks = []
    for label, key in [
        ("Guía / KEY", "guia"),
        ("Fecha", "fecha"),
        ("Supervisor", "supervisor"),
        ("Almacén", "almacen"),
        ("Material", "material"),
        ("Cantidad", "cantidad"),
        ("Estado", "estado")
    ]:
        checks.append({
            "Campo": label,
            "Anterior": old_a["cols"].get(key) or "No encontrada",
            "Actual": new_a["cols"].get(key) or "No encontrada"
        })

    st.dataframe(
        pd.DataFrame(checks),
        use_container_width=True,
        hide_index=True
    )

    # Comparación por dimensiones
    st.subheader("🏆 ¿Dónde cambió la carga?")

    tabs = st.tabs(["Supervisores", "Materiales", "Almacenes"])

    for tab, key, title in zip(
        tabs,
        ["supervisor", "material", "almacen"],
        ["Supervisor", "Material", "Almacén"]
    ):
        with tab:
            old_table = group_analysis(
                previous["df"], old_a["cols"], key
            )
            new_table = group_analysis(
                current["df"], new_a["cols"], key
            )

            if old_table is None or new_table is None:
                st.warning(f"No se pudo analizar por {title.lower()}.")
            else:
                old_col = old_table.columns[0]
                val_col_old = old_table.columns[-1]
                new_col = new_table.columns[0]
                val_col_new = new_table.columns[-1]

                old_table = old_table.rename(
                    columns={old_col: title, val_col_old: "Anterior"}
                )
                new_table = new_table.rename(
                    columns={new_col: title, val_col_new: "Actual"}
                )

                comp = pd.merge(
                    old_table,
                    new_table,
                    on=title,
                    how="outer"
                ).fillna(0)

                comp["Diferencia"] = comp["Actual"] - comp["Anterior"]

                def pct_row(row):
                    if row["Anterior"] == 0:
                        return np.nan if row["Actual"] != 0 else 0
                    return row["Diferencia"] / row["Anterior"] * 100

                comp["Variación %"] = comp.apply(pct_row, axis=1)
                comp = comp.sort_values(
                    "Actual", ascending=False
                )

                st.dataframe(
                    comp.head(50),
                    use_container_width=True,
                    hide_index=True
                )

    st.subheader("📋 Muestra de la carga actual")
    st.dataframe(
        current["df"].head(200),
        use_container_width=True,
        hide_index=True
    )

# ============================================================
# NOTAS
# ============================================================

with st.expander("ℹ️ Sobre los indicadores"):
    st.markdown("""
- **Guías:** se cuentan por valor único de `KEY` o `Guía`, si existe. No se usa el número de filas como número de guías.
- **Unidades:** se suman desde la columna `Cantidad` cuando existe.
- **Aprobadas:** solo se calculan si el archivo realmente contiene una columna `Estado` o equivalente.
- Si el detalle de salidas no trae `Estado` por línea, el dashboard **no inventa aprobaciones**.
- La comparación muestra **valor actual, diferencia absoluta, porcentaje y tendencia**.
- Los análisis por supervisor, material y almacén se calculan con los datos reales encontrados en el archivo.
""")
