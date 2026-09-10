# Dashboard Logística

Dashboard web para cargar archivos Excel y comparar una carga anterior contra una carga actual.

## Cómo usarlo

1. Abrir `index.html` en el navegador.
2. Pulsar **Cargar Excel**.
3. Seleccionar un archivo para ver el análisis actual.
4. Seleccionar dos archivos para comparar:
   - primero: carga anterior
   - segundo: carga actual
5. Los KPI muestran valor actual, diferencia absoluta y porcentaje de variación.

## Indicadores iniciales

- Total de guías
- Guías aprobadas
- Guías pendientes
- Unidades
- Materiales
- Encargados
- Almacenes
- Registros

## Importante

El lector busca automáticamente nombres comunes de columnas. Se puede adaptar `app.js` a los nombres exactos del Excel de logística.

El proyecto funciona en el navegador y no necesita servidor para hacer la primera prueba.
