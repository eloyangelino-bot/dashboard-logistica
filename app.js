const fileInput = document.getElementById("fileInput");
const statusBox = document.getElementById("status");
const kpis = document.getElementById("kpis");
const comparisonBody = document.querySelector("#comparisonTable tbody");
const currentBody = document.querySelector("#currentTable tbody");
const filesInfo = document.getElementById("filesInfo");
const comparisonText = document.getElementById("comparisonText");

fileInput.addEventListener("change", async (event) => {
  const files = [...event.target.files];
  if (!files.length) return;

  try {
    const datasets = [];
    for (const file of files.slice(0, 2)) {
      datasets.push({
        name: file.name,
        data: await readExcel(file)
      });
    }

    renderFiles(datasets);

    if (datasets.length === 1) {
      const current = calculateIndicators(datasets[0].data);
      renderCurrent(current);
      renderKpis(current, null);
      comparisonBody.innerHTML = "";
      comparisonText.textContent = "Se cargó una sola versión. Carga una segunda para comparar.";
      statusBox.textContent = `Carga actual: ${datasets[0].name}`;
    } else {
      // El usuario puede seleccionar dos archivos; el más antiguo queda como anterior.
      const previous = calculateIndicators(datasets[0].data);
      const current = calculateIndicators(datasets[1].data);
      renderCurrent(current);
      renderComparison(previous, current);
      renderKpis(current, previous);
      comparisonText.textContent =
        `${datasets[1].name} comparado contra ${datasets[0].name}.`;
      statusBox.textContent =
        "Comparación realizada: anterior → actual.";
    }
  } catch (error) {
    console.error(error);
    statusBox.textContent =
      "No se pudo leer el archivo. Verifica que sea un Excel (.xlsx/.xls) o CSV válido.";
  }
});

function readExcel(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();

    reader.onload = (e) => {
      try {
        const workbook = XLSX.read(e.target.result, { type: "array" });
        const firstSheet = workbook.Sheets[workbook.SheetNames[0]];
        const rows = XLSX.utils.sheet_to_json(firstSheet, { defval: "" });
        resolve(rows);
      } catch (err) {
        reject(err);
      }
    };

    reader.onerror = reject;
    reader.readAsArrayBuffer(file);
  });
}

function normalize(value) {
  return String(value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function findColumn(rows, candidates) {
  if (!rows.length) return null;
  const headers = Object.keys(rows[0]);

  for (const candidate of candidates) {
    const exact = headers.find(h => normalize(h) === normalize(candidate));
    if (exact) return exact;
  }

  for (const candidate of candidates) {
    const partial = headers.find(h =>
      normalize(h).includes(normalize(candidate))
    );
    if (partial) return partial;
  }

  return null;
}

function calculateIndicators(rows) {
  const guiaCol = findColumn(rows, [
    "guia", "nro guia", "numero guia", "número guia",
    "guia de remision", "guía de remisión"
  ]);

  const estadoCol = findColumn(rows, ["estado", "estatus", "status"]);
  const cantidadCol = findColumn(rows, [
    "cantidad", "cant", "unidades", "cantidad solicitada", "cantidad entregada"
  ]);
  const materialCol = findColumn(rows, [
    "material", "descripcion", "descripción", "producto", "item", "ítem"
  ]);
  const responsableCol = findColumn(rows, [
    "responsable", "encargado", "supervisor", "solicitante"
  ]);
  const almacenCol = findColumn(rows, [
    "almacen", "almacén", "centro", "almacen destino"
  ]);

  const unique = (col) => col
    ? new Set(rows.map(r => String(r[col]).trim()).filter(Boolean)).size
    : 0;

  const totalGuias = guiaCol
    ? unique(guiaCol)
    : rows.length;

  const totalUnidades = cantidadCol
    ? rows.reduce((sum, r) => sum + toNumber(r[cantidadCol]), 0)
    : 0;

  const aprobadas = estadoCol
    ? rows.filter(r => normalize(r[estadoCol]).includes("aprob")).length
    : 0;

  const pendientes = estadoCol
    ? rows.filter(r => {
        const s = normalize(r[estadoCol]);
        return s.includes("pend") || s.includes("proceso");
      }).length
    : 0;

  return {
    "Total guías": totalGuias,
    "Guías aprobadas": aprobadas,
    "Guías pendientes": pendientes,
    "Unidades": totalUnidades,
    "Materiales": unique(materialCol),
    "Encargados": unique(responsableCol),
    "Almacenes": unique(almacenCol),
    "Registros": rows.length
  };
}

function toNumber(value) {
  if (typeof value === "number") return value;
  let text = String(value ?? "").trim().replace(/\s/g, "");
  if (!text) return 0;

  // Soporta 1,250 / 1.250 / 1250,50 según el formato más común.
  if (text.includes(",") && text.includes(".")) {
    if (text.lastIndexOf(",") > text.lastIndexOf(".")) {
      text = text.replace(/\./g, "").replace(",", ".");
    } else {
      text = text.replace(/,/g, "");
    }
  } else if (text.includes(",")) {
    text = text.replace(",", ".");
  } else if ((text.match(/\./g) || []).length > 1) {
    text = text.replace(/\./g, "");
  }

  const number = Number(text.replace(/[^\d.-]/g, ""));
  return Number.isFinite(number) ? number : 0;
}

function formatNumber(value) {
  return new Intl.NumberFormat("es-PE", {
    maximumFractionDigits: 2
  }).format(value || 0);
}

function variation(previous, current) {
  const diff = current - previous;
  const pct = previous === 0
    ? (current === 0 ? 0 : null)
    : (diff / previous) * 100;
  return { diff, pct };
}

function renderKpis(current, previous) {
  const names = ["Total guías", "Guías aprobadas", "Unidades", "Materiales"];

  kpis.innerHTML = names.map(name => {
    const currentValue = current[name] ?? 0;

    if (!previous) {
      return `
        <div class="kpi">
          <div class="kpi-title">${name}</div>
          <div class="kpi-value">${formatNumber(currentValue)}</div>
          <div class="kpi-change flat">Sin comparación</div>
        </div>`;
    }

    const { diff, pct } = variation(previous[name] ?? 0, currentValue);
    const cls = diff > 0 ? "up" : diff < 0 ? "down" : "flat";
    const arrow = diff > 0 ? "↑" : diff < 0 ? "↓" : "→";
    const pctText = pct === null ? "N/D" : `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`;

    return `
      <div class="kpi">
        <div class="kpi-title">${name}</div>
        <div class="kpi-value">${formatNumber(currentValue)}</div>
        <div class="kpi-change ${cls}">
          ${arrow} ${diff >= 0 ? "+" : ""}${formatNumber(diff)}
          (${pctText} vs. carga anterior)
        </div>
      </div>`;
  }).join("");
}

function renderComparison(previous, current) {
  comparisonBody.innerHTML = Object.keys(current).map(name => {
    const oldValue = previous[name] ?? 0;
    const newValue = current[name] ?? 0;
    const { diff, pct } = variation(oldValue, newValue);

    const cls = diff > 0 ? "up" : diff < 0 ? "down" : "flat";
    const arrow = diff > 0 ? "↑" : diff < 0 ? "↓" : "→";
    const pctText = pct === null ? "N/D" : `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`;

    return `
      <tr>
        <td><strong>${name}</strong></td>
        <td>${formatNumber(oldValue)}</td>
        <td>${formatNumber(newValue)}</td>
        <td class="${cls}">${diff >= 0 ? "+" : ""}${formatNumber(diff)}</td>
        <td class="${cls}">${pctText}</td>
        <td class="${cls}">${arrow} ${diff > 0 ? "Aumenta" : diff < 0 ? "Disminuye" : "Sin cambio"}</td>
      </tr>`;
  }).join("");
}

function renderCurrent(current) {
  currentBody.innerHTML = Object.entries(current).map(([name, value]) => `
    <tr>
      <td>${name}</td>
      <td><strong>${formatNumber(value)}</strong></td>
    </tr>
  `).join("");
}

function renderFiles(datasets) {
  filesInfo.innerHTML = datasets.map((item, index) => `
    <div>
      <span class="badge">${index === 0 && datasets.length > 1 ? "ANTERIOR" : "ACTUAL"}</span>
      ${escapeHtml(item.name)}
      <small> — ${item.data.length.toLocaleString("es-PE")} registros</small>
    </div>
  `).join("");
}

function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, ch => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
  }[ch]));
}
