# Dashboard Logística — Matriz de Guías Únicas

Dashboard Streamlit para analizar despachos por sede, estado y encargado.

## Regla de negocio
**1 guía única = P. Emis + Número**

Una guía puede aparecer en muchas filas porque contiene varios materiales. Esas filas se consolidan y la guía se cuenta una sola vez.

## Columnas obligatorias
- `P. Emis`
- `Número`
- `F.Almac.`

Columnas analizadas cuando existen:
- `Estado`
- `Doc . Encargado`
- `Encargado`
- `C. Alm`
- `Almacen`

Los campos de materiales no se usan para contar guías.

## Ejecutar
```bash
pip install -r requirements.txt
streamlit run app.py
```

En Streamlit Cloud:
- Main file path: `app.py`
