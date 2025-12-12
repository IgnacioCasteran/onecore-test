// =====================
// CONFIG
// =====================
const API_URL = "http://127.0.0.1:8000";
let accessToken = null;

async function apiFetch(path, options = {}) {
  const url = `${API_URL}${path}`;
  const headers = options.headers ? { ...options.headers } : {};
  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }
  const resp = await fetch(url, { ...options, headers });
  if (!resp.ok) {
    const errText = await resp.text().catch(() => "");
    console.error("apiFetch error", resp.status, errText);
    throw new Error(`HTTP ${resp.status} ${resp.statusText} - ${errText || ""}`);
  }
  return resp;
}

// =====================
// LOGIN
// =====================
const loginForm = document.getElementById("login-form");
const loginStatus = document.getElementById("login-status");
const tokenIndicator = document.getElementById("token-indicator");

loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  loginStatus.textContent = "Iniciando sesión...";
  loginStatus.className = "status";

  try {
    // backend actual: /auth/login sin body, igual que Swagger Try it out
    const resp = await fetch(`${API_URL}/auth/login`, {
      method: "POST",
      headers: { Accept: "application/json" },
    });

    if (!resp.ok) {
      const err = await resp.text().catch(() => "");
      console.error("Login error", resp.status, err);
      loginStatus.textContent = `Error: ${resp.status} ${resp.statusText}`;
      loginStatus.className = "status error";
      accessToken = null;
      tokenIndicator.style.display = "none";
      return;
    }

    const data = await resp.json();
    console.log("Login response", data);

    if (!data.token || !data.token.access_token) {
      loginStatus.textContent = "No se recibió access_token";
      loginStatus.className = "status error";
      accessToken = null;
      tokenIndicator.style.display = "none";
      return;
    }

    accessToken = data.token.access_token;
    loginStatus.textContent = `Login OK (usuario id ${data.id_usuario})`;
    loginStatus.className = "status ok";
    tokenIndicator.style.display = "inline-flex";
  } catch (err) {
    console.error(err);
    loginStatus.textContent = "Error: Failed to fetch";
    loginStatus.className = "status error";
    accessToken = null;
    tokenIndicator.style.display = "none";
  }
});

// =====================
// ANALIZAR DOCUMENTO
// =====================
const analyzeForm = document.getElementById("analyze-form");
const analyzeStatus = document.getElementById("analyze-status");
const analyzeResultBox = document.getElementById("analyze-result");
const analyzeJsonPre = document.getElementById("analyze-json");
const analyzeSummaryDiv = document.getElementById("analyze-summary");

/**
 * Intenta extraer datos de factura desde el texto OCR.
 * Está pensado para casos como:
 *  - Factura AFIP (PABLO A SUCHMANS)
 *  - Factura proforma Tiendanube
 */
function parseInvoiceFromText(rawText) {
  if (!rawText) return {};

  const text = rawText
    .replace(/\r/g, "\n")
    .replace(/[ \t]+/g, " ");

  const lines = text.split("\n").map(l => l.trim()).filter(Boolean);
  const lowerLines = lines.map(l => l.toLowerCase());

  let client = "";
  let provider = "";
  let number = "";
  let date = "";
  let total = "";

  // --- Cliente ---
  for (let i = 0; i < lowerLines.length; i++) {
    const l = lowerLines[i];
    if (l.startsWith("cliente")) {
      const raw = lines[i];
      const afterColon = raw.split(":")[1];
      if (afterColon && afterColon.trim()) {
        client = afterColon.trim();
      } else if (lines[i + 1]) {
        client = lines[i + 1].trim();
      }
      break;
    }
  }

  // --- Proveedor / Emisor / Razón social ---
  for (let i = 0; i < lowerLines.length && !provider; i++) {
    const l = lowerLines[i];
    if (l.startsWith("razon social") || l.startsWith("razón social")) {
      const raw = lines[i];
      const afterColon = raw.split(":")[1];
      if (afterColon && afterColon.trim()) {
        provider = afterColon.trim();
      } else if (lines[i + 1]) {
        provider = lines[i + 1].trim();
      }
    } else if (l === "emisor" || l.startsWith("emisor")) {
      // Factura Tiendanube
      if (lines[i + 2]) {
        provider = lines[i + 2].trim();
      }
    }
  }

  // --- Número de factura / comprobante ---
  const numberRegexes = [
    /(comprobante)\s*[:\-]?\s*(.+)/i,
    /(n[º°o]?\s*factura|n[º°o]?\s*de\s*factura|numero de factura)\s*[:\-]?\s*(.+)/i
  ];
  for (const line of lines) {
    for (const re of numberRegexes) {
      const m = line.match(re);
      if (m && m[2]) {
        number = m[2].trim();
        break;
      }
    }
    if (number) break;
  }

  // --- Fecha ---
  const dateRegex = /(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4})/;
  for (const line of lines) {
    const low = line.toLowerCase();
    if (
      low.includes("fecha emision") ||
      low.includes("fecha emisión") ||
      low.includes("fecha de emision") ||
      low.includes("fecha de emisión")
    ) {
      const m = line.match(dateRegex);
      if (m) {
        date = m[1];
        break;
      }
    }
  }
  if (!date) {
    for (const line of lines) {
      const m = line.match(dateRegex);
      if (m) {
        date = m[1];
        break;
      }
    }
  }

  // --- Total ---
  // Primero buscamos "Importe Total"
  for (const line of lines) {
    if (/importe\s+total/i.test(line)) {
      const m = line.match(/([\d]{1,3}([\.\,]\d{3})*([\.\,]\d{2})?)/);
      if (m) {
        total = m[1];
      }
    }
  }
  // Luego "Total" (evitando "Total con letras" y "Subtotal")
  if (!total) {
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const low = lowerLines[i];

      if (
        low.startsWith("total") &&
        !low.includes("con letras") &&
        !low.includes("subtotal")
      ) {
        let candidate = "";
        const inline = line.match(/([\d]{1,3}([\.\,]\d{3})*([\.\,]\d{2})?)/);
        if (inline) {
          candidate = inline[1];
        } else if (lines[i + 1]) {
          const mNext = lines[i + 1].match(/([\d]{1,3}([\.\,]\d{3})*([\.\,]\d{2})?)/);
          if (mNext) candidate = mNext[1];
        }
        if (candidate) {
          total = candidate;
        }
      }
    }
  }

  return { client, provider, number, date, total };
}

analyzeForm.addEventListener("submit", async (e) => {
  e.preventDefault();

  analyzeResultBox.style.display = "none";
  analyzeJsonPre.textContent = "";
  analyzeSummaryDiv.innerHTML = "";

  if (!accessToken) {
    analyzeStatus.textContent = "Error: primero iniciá sesión.";
    analyzeStatus.className = "status error";
    return;
  }

  const fileInput = document.getElementById("doc-file");
  if (!fileInput.files.length) {
    analyzeStatus.textContent = "Seleccioná un archivo primero.";
    analyzeStatus.className = "status error";
    return;
  }

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);
  formData.append(
    "description",
    document.getElementById("doc-description").value || ""
  );

  analyzeStatus.textContent = "Analizando documento...";
  analyzeStatus.className = "status";

  try {
    const resp = await apiFetch("/documents/analyze", {
      method: "POST",
      body: formData,
    });
    const data = await resp.json();

    analyzeStatus.textContent = "Análisis completado.";
    analyzeStatus.className = "status ok";

    renderAnalyzeSummary(data);
    analyzeJsonPre.textContent = JSON.stringify(data, null, 2);
    analyzeResultBox.style.display = "block";
  } catch (err) {
    console.error(err);
    analyzeStatus.textContent = err.message;
    analyzeStatus.className = "status error";
  }
});

// Tarjeta resumen bonita según tipo de doc
function renderAnalyzeSummary(data) {
  if (!data || !data.extracted) {
    analyzeSummaryDiv.innerHTML =
      "<p>No se recibieron datos de análisis.</p>";
    return;
  }

  const e = data.extracted || {};
  const rawType = e.doc_type || data.doc_type || "desconocido";
  const kind = rawType.toLowerCase();
  const filename = data.filename || "-";

  let html = `
    <h4>Resumen de análisis</h4>
    <dl>
      <dt>Archivo</dt><dd>${filename}</dd>
      <dt>Tipo detectado</dt><dd>${rawType}</dd>
    </dl>
  `;

  if (kind === "factura") {
    const parsed = parseInvoiceFromText(e.text || "");
    const cliente   = e.cliente        || parsed.client   || "-";
    const proveedor = e.proveedor      || parsed.provider || "-";
    const numero    = e.numero_factura || parsed.number   || "-";
    const fecha     = e.fecha          || parsed.date     || "-";
    const total     = e.total          || parsed.total    || "-";

    html += `
      <h4 style="margin-top:10px;">Datos de factura</h4>
      <dl>
        <dt>Cliente</dt><dd>${cliente}</dd>
        <dt>Proveedor</dt><dd>${proveedor}</dd>
        <dt>N° factura</dt><dd>${numero}</dd>
        <dt>Fecha</dt><dd>${fecha}</dd>
        <dt>Total</dt><dd>${total}</dd>
      </dl>
    `;
  } else {
    html += `
      <h4 style="margin-top:10px;">Contenido</h4>
      <dl>
        <dt>Descripción</dt><dd>${e.description || "(sin descripción)"}</dd>
        <dt>Texto OCR</dt><dd>${(e.text || "").slice(0, 400) || "(sin texto)"}</dd>
      </dl>
    `;
  }

  analyzeSummaryDiv.innerHTML = html;
}

// =====================
// TABS
// =====================
const tabButtons = document.querySelectorAll(".tab-btn");
const tabPanels = document.querySelectorAll(".tab-panel");

tabButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    const target = btn.dataset.tab;
    tabButtons.forEach((b) => b.classList.toggle("active", b === btn));
    tabPanels.forEach((p) => p.classList.toggle("active", p.id === target));
  });
});

// =====================
// LISTA DE EVENTOS
// =====================
const eventsFilterForm = document.getElementById("events-filter-form");
const eventsStatus = document.getElementById("events-status");
const eventsWrapper = document.getElementById("events-wrapper");
const eventsTbody = document.getElementById("events-tbody");
const eventsEmpty = document.getElementById("events-empty");
const btnClearFilters = document.getElementById("btn-clear-filters");

function buildEventsParamsFromFilters() {
  const params = new URLSearchParams();
  const type = document.getElementById("event-type").value;
  const desc = document.getElementById("event-text").value.trim();
  const fromDate = document.getElementById("date-from").value;
  const toDate = document.getElementById("date-to").value;

  if (type) params.append("event_type", type);
  if (desc) params.append("description", desc);
  if (fromDate) params.append("date_from", fromDate);
  if (toDate) params.append("date_to", toDate);

  return params;
}

eventsFilterForm.addEventListener("submit", async (e) => {
  e.preventDefault();

  if (!accessToken) {
    eventsStatus.textContent = "Error: primero iniciá sesión.";
    eventsStatus.className = "status error";
    return;
  }

  const params = buildEventsParamsFromFilters();
  const query = params.toString() ? `?${params.toString()}` : "";

  eventsStatus.textContent = "Cargando eventos...";
  eventsStatus.className = "status";
  eventsEmpty.style.display = "none";
  eventsTbody.innerHTML = "";

  try {
    const resp = await apiFetch(`/events${query}`, { method: "GET" });
    const data = await resp.json();

    if (!Array.isArray(data) || data.length === 0) {
      eventsStatus.textContent = "No se encontraron eventos.";
      eventsStatus.className = "status";
      eventsWrapper.style.display = "none";
      eventsEmpty.style.display = "block";
      return;
    }

    data.forEach((evt) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${evt.id}</td>
        <td><span class="event-type-pill">${evt.event_type}</span></td>
        <td>${evt.description || ""}</td>
        <td>${evt.created_at || ""}</td>
      `;
      eventsTbody.appendChild(tr);
    });

    eventsStatus.textContent = `${data.length} evento(s) encontrados.`;
    eventsStatus.className = "status ok";
    eventsWrapper.style.display = "block";
    eventsEmpty.style.display = "none";
  } catch (err) {
    console.error(err);
    eventsStatus.textContent = err.message;
    eventsStatus.className = "status error";
    eventsWrapper.style.display = "none";
    eventsEmpty.style.display = "block";
  }
});

btnClearFilters.addEventListener("click", () => {
  document.getElementById("event-type").value = "";
  document.getElementById("event-text").value = "";
  document.getElementById("date-from").value = "";
  document.getElementById("date-to").value = "";

  eventsStatus.textContent = "";
  eventsTbody.innerHTML = "";
  eventsWrapper.style.display = "none";
  eventsEmpty.style.display = "block";
});

// =====================
// EXPORTAR A EXCEL
// =====================
const exportForm = document.getElementById("export-form");
const exportStatus = document.getElementById("export-status");

function buildExportParams() {
  const params = new URLSearchParams();
  const type = document.getElementById("export-type").value;
  const fromDate = document.getElementById("export-from").value;
  const toDate = document.getElementById("export-to").value;

  if (type) params.append("event_type", type);
  if (fromDate) params.append("date_from", fromDate);
  if (toDate) params.append("date_to", toDate);

  return params;
}

exportForm.addEventListener("submit", async (e) => {
  e.preventDefault();

  if (!accessToken) {
    exportStatus.textContent = "Error: primero iniciá sesión.";
    exportStatus.className = "status error";
    return;
  }

  const params = buildExportParams();
  const query = params.toString() ? `?${params.toString()}` : "";

  exportStatus.textContent = "Generando Excel...";
  exportStatus.className = "status";

  try {
    const resp = await apiFetch(`/events/export${query}`, {
      method: "GET",
    });
    const blob = await resp.blob();

    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "eventos.xlsx";
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);

    exportStatus.textContent = "Excel descargado correctamente.";
    exportStatus.className = "status ok";
  } catch (err) {
    console.error(err);
    exportStatus.textContent = err.message;
    exportStatus.className = "status error";
  }
});
