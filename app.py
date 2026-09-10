import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="Dashboard Logística",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Dashboard Logística")
st.caption("Carga actual vs. carga anterior")

def normalizar(valor):
    texto = str(valor).strip().lower()
    for a, b in {"á":"a","é":"e","í":"i","ó":"o","ú":"u","ñ":"n"}.items():
        texto = texto.replace(a, b)
    return texto

def buscar_columna(df, opciones):
    columnas = list(df.columns)

    for opcion in opciones:
        for columna in columnas:
            if normalizar(columna) == normalizar(opcion):
                return columna

    for opcion in opciones:
        for columna in columnas:
            if normalizar(opcion) in normalizar(columna):
                return columna

    return None

def numero(valor):
    if pd.isna(valor) or str(valor).strip() == "":
        return 0

    texto = str(valor).strip().replace("S/", "").replace(" ", "")

    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        texto = texto.replace(",", ".")

    try:
        return float(texto)
    except:
        return 0

def indicadores(df):
    guia = buscar_columna(df, [
        "guia", "nro guia", "numero guia",
        "guia de remision", "guía de remisión"
    ])

    estado = buscar_columna(df, [
        "estado", "estatus", "status"
    ])

    cantidad = buscar_columna(df, [
        "cantidad", "cant", "unidades",
        "cantidad solicitada", "cantidad entregada"
    ])

    material = buscar_columna(df, [
        "material", "descripcion", "descripción",
        "producto", "item", "ítem"
    ])

    responsable = buscar_columna(df, [
        "responsable", "encargado",
        "supervisor", "solicitante"
    ])

    almacen = buscar_columna(df, [
        "almacen", "almacén",
        "almacen destino", "centro"
    ])

    def unicos(columna):
        if not columna:
            return 0

        valores = (
            df[columna]
            .astype(str)
            .str.strip()
        )

        valores = valores[valores != ""]
        return int(valores.nunique())

    if guia:
        total_guias = unicos(guia)
    else:
        total_guias = len(df)

    if cantidad:
        unidades = df[cantidad].apply(numero).sum()
    else:
        unidades = 0

    aprobadas = 0
    pendientes = 0

    if estado:
        estados = df[estado].astype(str).map(normalizar)

        aprobadas = int(
            estados.str.contains("aprob", na=False).sum()
        )

        pendientes = int(
            (
                estados.str.contains("pend", na=False)
                |
                estados.str.contains("proceso", na=False)
            ).sum()
        )

    return {
        "Total guías": total_guias,
        "Guías aprobadas": aprobadas,
        "Guías pendientes": pendientes,
        "Unidades": unidades,
        "Materiales": unicos(material),
        "Encargados": unicos(responsable),
        "Almacenes": unicos(almacen),
        "Registros": len(df)
    }

def formato(valor):
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def comparar(anterior, actual):
    resultado = []

    for indicador in actual.keys():
        viejo = anterior.get(indicador, 0)
        nuevo = actual.get(indicador, 0)

        diferencia = nuevo - viejo

        if viejo == 0:
            porcentaje = None if nuevo != 0 else 0
        else:
            porcentaje = (diferencia / viejo) * 100

        if diferencia > 0:
            tendencia = "🟢 ↑ Aumenta"
        elif diferencia < 0:
            tendencia = "🔴 ↓ Disminuye"
        else:
            tendencia = "⚪ → Sin cambio"

        resultado.append({
            "Indicador": indicador,
            "Anterior": formato(viejo),
            "Actual": formato(nuevo),
            "Diferencia": f"{diferencia:+,.2f}",
            "Variación": (
                "N/D"
                if porcentaje is None
                else f"{porcentaje:+.2f}%"
            ),
            "Tendencia": tendencia
        })

    return pd.DataFrame(resultado)

# ============================================================
# CARGA DE ARCHIVOS
# ============================================================

archivos = st.file_uploader(
    "📂 Cargar Excel",
    type=["xlsx", "xls", "csv"],
    accept_multiple_files=True
)

if not archivos:
    st.info(
        "Carga un Excel para analizarlo. "
        "Carga dos archivos para comparar: primero el anterior y luego el actual."
    )
    st.stop()

datos = []

for archivo in archivos[:2]:

    try:
        if archivo.name.lower().endswith(".csv"):
            df = pd.read_csv(archivo)
        else:
            df = pd.read_excel(archivo)

        datos.append((archivo.name, df))

    except Exception as error:
        st.error(f"Error leyendo {archivo.name}: {error}")

if not datos:
    st.stop()

# ============================================================
# UNA SOLA CARGA
# ============================================================

if len(datos) == 1:

    nombre, df = datos[0]
    actual = indicadores(df)

    st.success(
        f"Carga actual: {nombre} | "
        f"{len(df):,} registros".replace(",", ".")
    )

    columnas = st.columns(4)

    for columna, indicador in zip(
        columnas,
        ["Total guías", "Guías aprobadas", "Unidades", "Materiales"]
    ):
        columna.metric(
            indicador,
            formato(actual[indicador])
        )

    st.subheader("📋 Resumen actual")

    tabla = pd.DataFrame({
        "Indicador": list(actual.keys()),
        "Valor": [formato(v) for v in actual.values()]
    })

    st.dataframe(
        tabla,
        use_container_width=True,
        hide_index=True
    )

# ============================================================
# COMPARACIÓN
# ============================================================

else:

    nombre_anterior, df_anterior = datos[0]
    nombre_actual, df_actual = datos[1]

    anterior = indicadores(df_anterior)
    actual = indicadores(df_actual)

    st.success(
        f"Actual: {nombre_actual}  |  "
        f"Anterior: {nombre_anterior}"
    )

    st.subheader("📊 Indicadores principales")

    columnas = st.columns(4)

    for columna, indicador in zip(
        columnas,
        ["Total guías", "Guías aprobadas", "Unidades", "Materiales"]
    ):

        viejo = anterior[indicador]
        nuevo = actual[indicador]

        diferencia = nuevo - viejo

        if viejo == 0:
            delta = "N/D"
        else:
            porcentaje = diferencia / viejo * 100
            delta = f"{diferencia:+,.2f} ({porcentaje:+.2f}%)"

        columna.metric(
            indicador,
            formato(nuevo),
            delta
        )

    st.subheader("📈 Comparación completa")

    tabla_comparacion = comparar(
        anterior,
        actual
    )

    st.dataframe(
        tabla_comparacion,
        use_container_width=True,
        hide_index=True
    )

    st.subheader("📋 Resumen de la carga actual")

    tabla_actual = pd.DataFrame({
        "Indicador": list(actual.keys()),
        "Valor": [formato(v) for v in actual.values()]
    })

    st.dataframe(
        tabla_actual,
        use_container_width=True,
        hide_index=True
    )

st.divider()

st.caption(
    "Versión inicial. Los nombres de columnas se detectan automáticamente."
)
