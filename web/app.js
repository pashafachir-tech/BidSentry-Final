import { api, setAuthToken, downloadDocument, decodeText } from "./api.js?v=4.2.0";
import { getState, setState, subscribe, resetWorkspaceState } from "./state.js?v=4.2.0";
import { renderApp, renderDialogs, renderLogin, escapeHtml } from "./render.js?v=4.2.0";
import { getReviewSnapshot } from "./review.js?v=4.2.0";

const root = document.getElementById("app");
const dialogLayer = document.getElementById("dialog-layer");
const toastNode = document.getElementById("toast");
const auditMemoryCache = new Map();

window.addEventListener("bidsentry:auth-required", () => {
  const token = window.prompt("Autentikasi diperlukan. Masukkan Token Akses (BIDSENTRY_ACCESS_TOKEN):");
  if (token) {
    setAuthToken(token);
    toast("Token akses telah disimpan di sesi memori.");
    loadWorkspace();
  }
});

const uploadedFiles = { dok_pemilihan: [], adendum: [], pustaka: [], contract_draft: [], baseline_contract: [] };
const uploadErrors = { dok_pemilihan: [], adendum: [], pustaka: [], contract_draft: [], baseline_contract: [] };
const dragCounters = {};
let pendingReplace = null;
let pendingDeleteAudit = null;
let toastTimer = null;
let searchDebounceTimer = null;

const SUPPORTED_EXTENSIONS = new Set([".pdf", ".docx", ".xlsx", ".txt", ".md", ".csv", ".json"]);
const MAX_DOCUMENT_BYTES = 8 * 1024 * 1024;
const auditSubmitReadyMarkup = 'Jalankan evaluasi <svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>';
const MAX_FILES_PER_UPLOAD = 20;
const MAX_PARALLEL_EXTRACTIONS = 3;
let workspaceRequestSequence = 0;
let activeUploads = 0;
let pendingDispatchPayload = null;
let dispatchInProgress = false;

try {
  document.documentElement.dataset.theme = localStorage.getItem("bidsentry-theme") === "dark" ? "dark" : "light";
} catch {
  document.documentElement.dataset.theme = "light";
}

// Initial render of dialog layer (isolated from main app re-renders per Requirement 3.4)
if (dialogLayer) {
  dialogLayer.innerHTML = renderDialogs(getState());
}

function render() {
  const active = document.activeElement;
  const id = active?.id;
  const start = typeof active?.selectionStart === "number" ? active.selectionStart : null;
  const action = root.contains(active) ? active?.dataset?.action : null;
  const actionIndex = action
    ? [...root.querySelectorAll("[data-action]")].filter((node) => node.dataset.action === action).indexOf(active)
    : -1;

  const current = getState();
  if (!current.sessionChecked) {
    root.innerHTML = '<main class="boot-screen"><div class="boot-brand">BidSentry</div><p>Memeriksa sesi…</p></main>';
    return;
  }
  root.innerHTML = current.session?.authenticated ? renderApp(current) : renderLogin(current);

  const next = (id && document.getElementById(id)) || (action && [...root.querySelectorAll("[data-action]")].filter((node) => node.dataset.action === action)[actionIndex]);
  if (next && root.contains(next)) {
    next.focus({ preventScroll: true });
    if (start !== null && typeof next.setSelectionRange === "function") next.setSelectionRange(start, start);
  }
}

subscribe(render);

// Error and notification toast with persistence and manual dismiss (Requirement 3.6)
function toast(message, kind = "success") {
  if (toastTimer) clearTimeout(toastTimer);
  toastNode.className = "toast";
  void toastNode.offsetWidth;
  toastNode.innerHTML = `<span>${escapeHtml(message)}</span><button type="button" class="toast-close" data-action="close-toast" aria-label="Tutup pesan">✕</button>`;
  toastNode.className = `toast toast-visible ${kind === "error" ? "toast-error" : ""}`;
  const duration = kind === "error" ? 10000 : 4000;
  toastTimer = setTimeout(() => {
    toastNode.className = "toast";
  }, duration);
}

async function selectAudit(auditId) {
  if (!auditId) return;
  const state = getState();
  const cachedRow = (state.audits || []).find((row) => row.audit_id === auditId);
  const payload = auditMemoryCache.get(auditId) || cachedRow || null;

    setState({
    selectedAuditId: auditId,
    currentAudit: payload,
    customReview: payload,
    reviewFilter: "ALL",
    expandedFindingId: null,
    proof: null,
  });
  if (getState().reviewTab === "proof") loadProof(auditId);
  loadEconomics(auditId);

  try {
    const full = await api.getAudit(auditId);
    if (full) {
      auditMemoryCache.set(auditId, full);
      if (getState().selectedAuditId === auditId) {
        setState({
          currentAudit: full,
          customReview: full,
        });
      }
    }
  } catch {
    // If offline or error, state already has payload/cachedRow
  }

  try {
    const reviewFeedback = await api.reviewFeedback(auditId);
    if (getState().selectedAuditId === auditId) {
      setState({ reviewFeedback });
    }
  } catch {
    if (getState().selectedAuditId === auditId) {
      setState({ reviewFeedback: null });
    }
  }
}

async function loadWorkspace({ preserveSelection = true, includeOverview = true, includeHealth = true, includeFeedback = true } = {}) {
  const requestSequence = ++workspaceRequestSequence;
  setState({ loading: true });
  const state = getState();
  try {
    if (!getState().benchmark) api.benchmarkSummary().then((benchmark) => setState({ benchmark })).catch(() => setState({ benchmark: { status: "unavailable", message: "Ringkasan benchmark tidak dapat dimuat." } }));
    const [overview, audits, health, reviewFeedback] = await Promise.all([
      includeOverview ? api.overview() : Promise.resolve(state.overview),
      api.audits({ q: state.query, risk: state.riskFilter }),
      includeHealth ? api.health() : Promise.resolve(null),
      includeFeedback ? api.reviewFeedback(state.customReview?.audit_id || "").catch(() => null) : Promise.resolve(state.reviewFeedback),
    ]);
    if (requestSequence !== workspaceRequestSequence) return;
    const selected = preserveSelection && audits.audits.some((row) => row.audit_id === state.selectedAuditId)
      ? state.selectedAuditId : audits.audits[0]?.audit_id || null;
    const selectedAuditObj = (audits.audits || []).find((row) => row.audit_id === selected) || null;
    setState({
      ...(includeOverview ? { overview } : {}),
      audits: audits.audits,
      selectedAuditId: selected,
      ...(!state.customReview || !preserveSelection ? { customReview: selectedAuditObj, currentAudit: selectedAuditObj } : {}),
      ...(includeHealth && health ? { integrations: health.integrations } : {}),
      ...(includeFeedback ? { reviewFeedback } : {}),
      loading: false,
    });
    if (selected && getState().economics?.audit_id !== selected) loadEconomics(selected);
  } catch (error) {
    if (requestSequence !== workspaceRequestSequence) return;
    setState({ loading: false });
    toast(error.message, "error");
  }
}

// Modal delete confirmation (Requirement 3.6 - no blocking confirm())
function deleteAuditRecord(auditId, packageName = "Audit ini") {
  if (!auditId) return;
  pendingDeleteAudit = { auditId, packageName };
  const targetTitle = document.getElementById("delete-target-title");
  if (targetTitle) targetTitle.textContent = `"${packageName}"`;
  const dialog = document.getElementById("confirm-delete-dialog");
  if (dialog?.showModal) dialog.showModal();
  else if (window.confirm(`Hapus pemeriksaan "${packageName}" dari riwayat?`)) {
    executeDeleteAudit();
  }
}

async function executeDeleteAudit() {
  if (!pendingDeleteAudit) return;
  const { auditId, packageName } = pendingDeleteAudit;
  document.getElementById("confirm-delete-dialog")?.close();
  try {
    await api.deleteAudit(auditId);
    auditMemoryCache.delete(auditId);
    toast(`Pemeriksaan "${packageName}" berhasil dihapus.`);
    const state = getState();
    const remainingAudits = (state.audits || []).filter((row) => row.audit_id !== auditId);
    const nextSelected = remainingAudits[0]?.audit_id || null;
    const nextSelectedObj = remainingAudits[0] || null;
    const isCustomActive = state.customReview?.audit_id === auditId;
    setState({
      audits: remainingAudits,
      selectedAuditId: nextSelected,
      currentAudit: isCustomActive ? nextSelectedObj : state.currentAudit,
      customReview: isCustomActive ? nextSelectedObj : state.customReview,
    });
    await loadWorkspace({ preserveSelection: false });
  } catch (error) {
    toast(error.message || "Gagal menghapus audit.", "error");
  } finally {
    pendingDeleteAudit = null;
  }
}

function openAuditDialog(draft = null) {
  const dialog = document.getElementById("audit-dialog");
  const form = document.getElementById("audit-form");
  if (draft && form) {
    for (const name of ["package_name", "tender_id", "notice_number", "pokja_name", "company_name", "contract_value_idr", "dok_pemilihan", "adendum", "pustaka", "contract_draft", "baseline_contract", "bid_deadline"]) {
      const field = form.elements.namedItem(name);
      if (field) field.value = draft[name] ?? "";
    }
    const extBox = form.elements.namedItem("allow_external_processing");
    if (extBox) extBox.checked = Boolean(draft.allow_external_processing);
    const roleSelect = form.elements.namedItem("review_role");
    if (roleSelect) roleSelect.value = draft.review_role || "procurement";
  }
  if (dialog?.showModal) dialog.showModal();
  else toast("Dialog audit tidak tersedia pada browser ini.", "error");
}

// 1-Click sample tender loader (Requirement 3.7)
function loadSampleTender() {
  const sampleTender = {
    package_name: "Pengadaan Server High Performance Computing (HPC)",
    tender_id: "HPC-2026-088",
    notice_number: "LPSE-KEMEN-2026-HPC",
    pokja_name: "Pokja Infrastruktur Digital",
    company_name: "PT Solusi Komputasi Nasional",
    contract_value_idr: 4500000000,
    review_role: "procurement",
    bid_deadline: "15 Agustus 2026",
    dok_pemilihan: `BAB III. SPESIFIKASI TEKNIS PERANGKAT SERVER HPC
1. Menggunakan prosesor Intel Xeon Emerald Rapids dengan arsitektur UPI 4.0 dan C741 chipset.
2. Dilengkapi akselerator GPU NVIDIA H100 SXM5 dengan interkoneksi eksklusif NVLink 4.0.
3. Manajemen sistem out-of-band wajib menggunakan Dell iDRAC 10 Platinum.

BAB IX. KETENTUAN JADWAL DAN PERSYARATAN
1. Masa penyusunan dan pemasukan penawaran adalah 3 hari kerja sejak pengumuman lelang.
2. Masa sanggah hasil lelang diberikan selama 2 hari kerja.
3. Peserta wajib melampirkan Nomor Induk Berusaha (NIB) dan NPWP aktif.

BAB X. ANGGARAN DAN RINCIAN BILL OF QUANTITIES (BoQ)
Pagu Anggaran DIPA tahun 2026 adalah sebesar Rp 4.500.000.000.
Total HPS hasil rekapitulasi BoQ adalah Rp 4.795.000.000.
Server HPC 2 soket | 4 unit | Rp 850.000.000 | Rp 3.400.000.000 | Rp 800.000.000
Switch InfiniBand 400G | 2 unit | Rp 420.000.000 | Rp 840.000.000 | Rp 410.000.000
Rak server 42U dan PDU | 3 set | Rp 95.000.000 | Rp 300.000.000 | Rp 95.000.000
Instalasi dan pelatihan | 1 paket | Rp 255.000.000 | Rp 255.000.000 | Rp 250.000.000`,
    pustaka: `Kredensial Dokumen Legal:
1. NPWP Perusahaan: 01.888.777.6-543.000 (status terdaftar)
2. Nomor Induk Berusaha (NIB): 9120001234567 (terdaftar OSS, status aktif)`,
    contract_draft: `BAB X. SANKSI DAN DENDA KETERLAMBATAN
1. Apabila Penyedia terlambat menyelesaikan pekerjaan, dikenakan denda keterlambatan sebesar 1/1000 per hari dari nilai kontrak tanpa batas maksimal.`,
    adendum: "",
    baseline_contract: "",
    allow_external_processing: false,
  };
  openAuditDialog(sampleTender);
  toast("Contoh tender simulasi berhasil dimuat. Klik 'Jalankan evaluasi' untuk memeriksa red flag.");
}

async function openSettingsDialog() {
  const dialog = document.getElementById("settings-dialog");
  if (!dialog) return;
  if (!dialog.open) dialog.showModal();

  const statusEl = document.getElementById("settings-file-status");
  if (statusEl) statusEl.textContent = "Memuat status konfigurasi tersimpan dari server...";

  try {
    const settings = await api.integrationSettings();
    const form = document.getElementById("settings-form");
    if (!form) return;
    const set = (name, value) => {
      const input = form.elements.namedItem(name);
      if (input) input.value = value ?? "";
    };
    const langflowEnabledInput = form.elements.namedItem("langflow_enabled");
    if (langflowEnabledInput) langflowEnabledInput.checked = Boolean(settings?.langflow?.enabled);

    set("langflow_url", settings?.langflow?.url);
    set("langflow_flow_id", settings?.langflow?.flow_id);
    set("langflow_api_key", "");
    set("langflow_timeout_seconds", settings?.langflow?.timeout_seconds);
    set("watsonx_api_key", "");
    set("watsonx_project_id", settings?.watsonx?.project_id || "");
    set("watsonx_url", settings?.watsonx?.url || "https://us-south.ml.cloud.ibm.com");
    set("watsonx_model_id", settings?.watsonx?.model_id || "mistralai/mistral-small-3-1-24b-instruct-2503");
    set("composio_api_key", "");
    set("composio_user_id", settings?.composio?.user_id);
    set("composio_base_url", settings?.composio?.base_url);
    set("composio_timeout_seconds", settings?.composio?.timeout_seconds);

    const clearLangflow = form.elements.namedItem("clear_langflow_api_key");
    if (clearLangflow) clearLangflow.checked = false;
    const clearWatsonx = form.elements.namedItem("clear_watsonx_api_key");
    if (clearWatsonx) clearWatsonx.checked = false;
    const clearComposio = form.elements.namedItem("clear_composio_api_key");
    if (clearComposio) clearComposio.checked = false;

    const langflowStatus = document.getElementById("langflow-key-status");
    if (langflowStatus) langflowStatus.textContent = settings?.langflow?.api_key_saved ? "API key tersimpan" : "API key belum diatur";
    const watsonxStatus = document.getElementById("watsonx-key-status");
    if (watsonxStatus) {
      watsonxStatus.textContent = settings?.watsonx?.api_key_saved
        ? "API key tersimpan"
        : "Belum diatur (Fallback Lokal Aktif)";
    }
    const composioStatus = document.getElementById("composio-key-status");
    if (composioStatus) composioStatus.textContent = settings?.composio?.api_key_saved ? "API key tersimpan" : "Belum dikonfigurasi";

    if (statusEl) {
      statusEl.textContent = settings?.config_file_exists
        ? "Disimpan ke file .env lokal dan dibaca tanpa restart. API key tidak pernah ditampilkan kembali."
        : "File .env akan dibuat saat disimpan. API key tidak pernah ditampilkan kembali.";
    }
  } catch (error) {
    if (statusEl) {
      statusEl.textContent = `Gagal memuat status server (${error.message || "koneksi terputus"}). Pastikan server BidSentry berjalan di 127.0.0.1:8000.`;
    }
    toast(error.message || "Pengaturan tidak dapat dimuat.", "error");
  }
}

async function saveSettings(form) {
  const values = new FormData(form);
  const payload = {
    langflow_enabled: values.get("langflow_enabled") === "on",
    langflow_url: String(values.get("langflow_url") || "").trim(),
    langflow_flow_id: String(values.get("langflow_flow_id") || "").trim(),
    langflow_api_key: String(values.get("langflow_api_key") || ""),
    clear_langflow_api_key: values.get("clear_langflow_api_key") === "on",
    langflow_timeout_seconds: Number(values.get("langflow_timeout_seconds")),
    watsonx_api_key: String(values.get("watsonx_api_key") || ""),
    clear_watsonx_api_key: values.get("clear_watsonx_api_key") === "on",
    watsonx_project_id: String(values.get("watsonx_project_id") || "").trim(),
    watsonx_url: String(values.get("watsonx_url") || "").trim(),
    watsonx_model_id: String(values.get("watsonx_model_id") || "").trim(),
    composio_api_key: String(values.get("composio_api_key") || ""),
    clear_composio_api_key: values.get("clear_composio_api_key") === "on",
    composio_user_id: String(values.get("composio_user_id") || "").trim(),
    composio_base_url: String(values.get("composio_base_url") || "").trim(),
    composio_timeout_seconds: Number(values.get("composio_timeout_seconds")),
  };
  const button = document.getElementById("save-settings");
  if (button) { button.disabled = true; button.textContent = "Menyimpan…"; }
  try {
    await api.saveIntegrationSettings(payload);
    document.getElementById("settings-dialog")?.close();
    toast("Pengaturan tersimpan ke .env. Status koneksi diperbarui.");
    await loadWorkspace({ includeOverview: false, includeFeedback: false });
  } catch (error) {
    toast(error.message || "Pengaturan gagal disimpan.", "error");
  } finally {
    if (button) { button.disabled = false; button.textContent = "Simpan koneksi"; }
  }
}

async function testIntegrations() {
  const button = document.getElementById("test-integrations");
  const output = document.getElementById("integrations-test-results");
  if (!button || !output) return;
  button.disabled = true;
  button.textContent = "Menguji…";
  output.hidden = false;
  output.textContent = "Menguji akses IBM watsonx, Langflow, dan Composio tanpa menjalankan aksi.";
  try {
    const result = await api.testIntegrations();
    const watsonx = result?.watsonx || {};
    const langflow = result?.langflow || {};
    const composio = result?.composio || {};
    output.textContent = [
      `IBM watsonx: ${watsonx.status || "unconfigured"} — ${watsonx.message || "Fallback lokal aktif."}`,
      `Langflow: ${langflow.status || "unknown"} — ${langflow.message || "Tidak ada detail."}`,
      `Composio: ${composio.status || "unknown"} — ${composio.message || "Tidak ada detail."}`,
      composio.linked_toolkits?.length ? `Toolkit aktif: ${composio.linked_toolkits.join(", ")}` : "",
    ].filter(Boolean).join("\n");
  } catch (error) {
    output.textContent = error.message || "Tes koneksi gagal.";
  } finally {
    button.disabled = false;
    button.textContent = "Tes koneksi";
  }
}

function formatFileSize(bytes) {
  if (typeof bytes !== "number" || isNaN(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  const unit = units[Math.min(i, units.length - 1)];
  const val = bytes / Math.pow(1024, unit === "B" ? 0 : unit === "KB" ? 1 : 2);
  return `${val < 10 && unit !== "B" ? val.toFixed(1) : Math.round(val)} ${unit}`;
}

function getFileIcon(filename) {
  const ext = (filename || "").slice((filename || "").lastIndexOf(".")).toLowerCase();
  if (ext === ".pdf") return "📄";
  if (ext === ".docx") return "📝";
  if (ext === ".xlsx") return "📊";
  if (ext === ".json") return "📋";
  if (ext === ".csv") return "📊";
  return "📑";
}

function getUploadedFiles(field) {
  if (!uploadedFiles[field]) uploadedFiles[field] = [];
  return uploadedFiles[field];
}

function getUploadErrors(field) {
  if (!uploadErrors[field]) uploadErrors[field] = [];
  return uploadErrors[field];
}

function getDragCounter(field) {
  return dragCounters[field] || 0;
}

function setDragCounter(field, count) {
  dragCounters[field] = Math.max(0, count);
  return dragCounters[field];
}

function validateFile(file) {
  if (!file) return { valid: false, message: "File tidak terbaca atau kosong." };
  const name = file.name || "";
  const lastDot = name.lastIndexOf(".");
  const ext = lastDot !== -1 ? name.slice(lastDot).toLowerCase() : "";
  if (!SUPPORTED_EXTENSIONS.has(ext)) {
    return {
      valid: false,
      message: `Format "${ext || "tanpa ekstensi"}" tidak didukung. Format didukung: PDF, DOCX, XLSX, TXT, MD, CSV, JSON.`,
    };
  }
  if (file.size > MAX_DOCUMENT_BYTES) {
    return {
      valid: false,
      message: `Ukuran file melebihi batas 8 MB (${formatFileSize(file.size)}).`,
    };
  }
  if (file.size === 0) {
    return {
      valid: false,
      message: "File kosong (0 byte).",
    };
  }
  return { valid: true };
}

function readTextFileLocally(file) {
  return new Promise((resolve, reject) => {
    let reader = new FileReader();
    reader.onload = () => {
      const result = reader?.result || "";
      reader = null;
      resolve(result);
    };
    reader.onerror = () => {
      reader = null;
      reject(new Error("File tidak dapat dibaca dari penyimpanan perangkat."));
    };
    reader.onabort = () => {
      reader = null;
      reject(new Error("Pembacaan file dibatalkan."));
    };
    try {
      reader.readAsText(file, "utf-8");
    } catch (err) {
      reader = null;
      reject(err);
    }
  });
}

async function extractSingleDocument(file) {
  const validation = validateFile(file);
  if (!validation.valid) {
    throw new Error(validation.message);
  }

  const name = file.name || "";
  const ext = name.slice(name.lastIndexOf(".")).toLowerCase();

  try {
    const data = await api.extractDocument(file);
    if (!data || typeof data.text !== "string") {
      throw new Error("Hasil ekstraksi dokumen kosong.");
    }
    return data;
  } catch (apiError) {
    if ([".txt", ".md", ".csv", ".json"].includes(ext)) {
      try {
        const text = await readTextFileLocally(file);
        let processedText = text.trim();
        if (!processedText) {
          throw new Error("File tidak memiliki konten teks.");
        }
        if (ext === ".json") {
          try {
            const parsed = JSON.parse(processedText);
            processedText = JSON.stringify(parsed, null, 2);
          } catch {
            // Keep original text
          }
        }
        return {
          filename: file.name,
          text: processedText,
          characters: processedText.length,
        };
      } catch (localError) {
        throw new Error(localError.message || apiError.message || "File teks tidak dapat dibaca.");
      }
    }
    throw new Error(apiError.message || "File dokumen tidak dapat diekstrak oleh sistem.");
  }
}

function clearUploadedFileLabels() {
  for (const field of Object.keys(uploadedFiles)) {
    uploadedFiles[field] = [];
    uploadErrors[field] = [];
    dragCounters[field] = 0;
    renderFileNames(field);
  }
  pendingReplace = null;
}

// File removal with textarea text sync (Requirement 3.3)
function removeUploadedFile(field, fileId, quiet = false) {
  const files = getUploadedFiles(field);
  const index = files.findIndex((f) => f.id === fileId);
  if (index === -1) return;
  const removed = files[index];
  files.splice(index, 1);

  const textarea = document.querySelector(`[name="${field}"]`);
  if (textarea) {
    textarea.value = files.map((f) => `--- ${f.name} ---\n${f.text}`).join("\n\n");
  }

  const input = document.querySelector(`[data-file-input="${field}"]`);
  if (input && files.length === 0) {
    input.value = "";
  }

  renderFileNames(field);
  if (!quiet) {
    toast(`File "${removed.name}" dihapus.`);
  }
}

function dismissUploadError(field, errorId) {
  const errors = getUploadErrors(field);
  const idx = errors.findIndex((e) => e.id === errorId);
  if (idx !== -1) {
    errors.splice(idx, 1);
    renderFileNames(field);
  }
}

function clearSlotSection(field) {
  uploadedFiles[field] = [];
  uploadErrors[field] = [];
  dragCounters[field] = 0;
  const textarea = document.querySelector(`[name="${field}"]`);
  if (textarea) textarea.value = "";
  const input = document.querySelector(`[data-file-input="${field}"]`);
  if (input) input.value = "";
  renderFileNames(field);
  toast(`Bagian ${field} dibersihkan.`);
}

// Render uploaded file objects with 3-line preview snippet (Requirement 3.3)
function renderFileNames(field) {
  const container = document.getElementById(`${field}-files`);
  if (!container) return;
  const files = getUploadedFiles(field);
  const errors = getUploadErrors(field);

  if (files.length === 0 && errors.length === 0) {
    container.innerHTML = "";
    return;
  }

  const fileItemsHtml = files.map((file) => `
    <div class="uploaded-file-item" data-file-id="${escapeHtml(file.id)}">
      <div class="uploaded-file-info">
        <span class="uploaded-file-icon" aria-hidden="true">${getFileIcon(file.name)}</span>
        <div class="uploaded-file-details">
          <div class="uploaded-file-name-row">
            <strong class="uploaded-file-name" title="${escapeHtml(file.name)}">${escapeHtml(file.name)}</strong>
            <span class="uploaded-file-meta">${escapeHtml(file.sizeFormatted)}${file.characters ? ` · ${new Intl.NumberFormat("id-ID").format(file.characters)} kar` : ""}</span>
          </div>
          ${file.preview ? `<div class="uploaded-file-preview">"${escapeHtml(file.preview.slice(0, 160))}..."</div>` : ""}
        </div>
      </div>
      <div class="uploaded-file-actions">
        <button type="button" class="file-action-btn file-action-remove" data-action="remove-file" data-field="${escapeHtml(field)}" data-file-id="${escapeHtml(file.id)}" title="Hapus file ini">✕</button>
      </div>
    </div>
  `).join("");

  const errorItemsHtml = errors.map((err) => `
    <div class="uploaded-file-error" data-error-id="${escapeHtml(err.id)}">
      <div class="uploaded-file-info">
        <span class="uploaded-file-error-icon" aria-hidden="true">⚠️</span>
        <span class="uploaded-file-error-msg">${err.name ? `<strong>${escapeHtml(err.name)}:</strong> ` : ""}${escapeHtml(err.message)}</span>
      </div>
      <div class="uploaded-file-actions">
        <button type="button" class="file-action-btn file-action-dismiss" data-action="dismiss-error" data-field="${escapeHtml(field)}" data-error-id="${escapeHtml(err.id)}" title="Tutup pesan error">✕</button>
      </div>
    </div>
  `).join("");

  container.innerHTML = fileItemsHtml + errorItemsHtml;
}

async function ingestFiles(fileList, field) {
  const rawFiles = [...(fileList || [])];
  const textarea = document.querySelector(`[name="${field}"]`);
  if (!textarea || !rawFiles.length) return;

  const currentFiles = getUploadedFiles(field);
  const currentErrors = getUploadErrors(field);

  if (pendingReplace && pendingReplace.field === field) {
    removeUploadedFile(field, pendingReplace.fileId, true);
    pendingReplace = null;
  }

  if (rawFiles.length > MAX_FILES_PER_UPLOAD) {
    currentErrors.push({
      id: `err-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      name: "",
      message: `Maksimal ${MAX_FILES_PER_UPLOAD} file dalam satu kali unggah.`,
    });
    renderFileNames(field);
    toast(`Pilih maksimal ${MAX_FILES_PER_UPLOAD} file dalam satu kali unggah.`, "error");
    return;
  }

  const submit = document.getElementById("submit-audit");
  activeUploads += 1;
  if (submit) {
    submit.disabled = true;
    submit.textContent = "Membaca file…";
  }

  const zone = document.querySelector(`.drop-zone[data-drop-target="${field}"]`);
  if (zone) zone.classList.add("is-reading");

  try {
    const results = [];
    for (let offset = 0; offset < rawFiles.length; offset += MAX_PARALLEL_EXTRACTIONS) {
      const batch = await Promise.all(
        rawFiles.slice(offset, offset + MAX_PARALLEL_EXTRACTIONS).map(async (file) => {
          try {
            const data = await extractSingleDocument(file);
            return { ok: true, file, data };
          } catch (error) {
            return { ok: false, file, error };
          }
        })
      );
      results.push(...batch);
    }

    let addedCount = 0;
    const warningsShown = [];
    for (const item of results) {
      if (item.ok && item.data.scanned_pdf && !(item.data.text || "").trim()) {
        // A scan without a text layer adds nothing to audit; explain instead of inserting placeholder text.
        currentErrors.push({
          id: `err-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
          name: item.file?.name || "",
          message: (item.data.warnings || [])[0] || "Dokumen pindaian tanpa lapisan teks; OCR belum tersedia.",
        });
        continue;
      }
      if (item.ok) {
        for (const warning of item.data.warnings || []) warningsShown.push(`${item.file.name}: ${warning}`);
        addedCount += 1;
        const text = item.data.text || "";
        const preview = text.split("\n").filter((l) => l.trim()).slice(0, 3).join(" ");
        currentFiles.push({
          id: `file-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
          name: item.file.name,
          size: item.file.size,
          sizeFormatted: formatFileSize(item.file.size),
          characters: item.data.characters || text.length,
          preview: preview,
          text: text,
        });
      } else {
        currentErrors.push({
          id: `err-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
          name: item.file?.name || "",
          message: item.error.message || "Gagal membaca dokumen.",
        });
      }
    }

    // Reconstruct textarea value from all file objects
    textarea.value = currentFiles.map((f) => `--- ${f.name} ---\n${f.text}`).join("\n\n");
    renderFileNames(field);

    if (warningsShown.length) {
      toast(warningsShown.slice(0, 2).join(" · "), "error");
    } else if (addedCount > 0) {
      toast(`${addedCount} dokumen berhasil diekstrak ke dalam slot.`);
    }
  } finally {
    activeUploads = Math.max(0, activeUploads - 1);
    if (zone) zone.classList.remove("is-reading");
    if (submit && activeUploads === 0) {
      submit.disabled = false;
      submit.innerHTML = auditSubmitReadyMarkup;
    }
  }
}

async function exportData() {
  const state = getState();
  try {
    const data = await api.audits({ q: state.query, risk: state.riskFilter });
    const workbook = await api.exportWorkbook({ kind: "register", audits: data.audits || [] });
    downloadDocument(workbook, "register-audit-bidsentry.xlsx");
    toast("Register audit Excel berhasil diunduh.");
  } catch (error) {
    toast(error.message, "error");
  }
}

async function exportReview() {
  const state = getState();
  const review = getReviewSnapshot(state);
  if (!review.isCustom) {
    toast("Pilih atau jalankan evaluasi terlebih dahulu.", "error");
    return;
  }
  try {
    const workbook = await api.exportWorkbook({ kind: "review", review });
    downloadDocument(workbook, `review-${review.id || "audit"}.xlsx`);
    toast("Laporan Risk Review Excel berhasil diunduh.");
  } catch (error) {
    toast(error.message, "error");
  }
}

async function exportSelectedReview() {
  const state = getState();
  const review = getReviewSnapshot(state);
  if (!review || !review.isCustom) {
    toast("Pilih audit dari tabel terlebih dahulu.", "error");
    return;
  }
  try {
    const workbook = await api.exportWorkbook({ kind: "review", review });
    downloadDocument(workbook, `risk-review-${review.tender_id || review.id || "audit"}.xlsx`);
    toast(`Risk Review "${review.package_name}" berhasil diekspor.`);
  } catch (error) {
    toast(error.message || "Gagal mengekspor laporan.", "error");
  }
}

function buildReviewPayload(row) {
  return {
    ...row,
    id: row.audit_id || "latest",
    package_name: row.package_name || "Evaluasi dokumen",
    verdict: row.executive_summary?.eligibility || row.verdict || "NEEDS_REVIEW",
    summary: row.executive_summary?.executive_summary || row.review_recommendation || "Periksa temuan.",
    findings: row.findings || [],
  };
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  requestAnimationFrame(() => URL.revokeObjectURL(url));
}

// Role-specific documents. Every document is generated and filtered by the server
// (role-gated, quote-verified); the browser never composes legal text itself.
function currentAuditId() {
  const review = getReviewSnapshot(getState());
  return review.isCustom ? (review.audit_id || "") : "";
}

async function withAudit(action) {
  const auditId = currentAuditId();
  if (!auditId) { toast("Pilih atau jalankan evaluasi terlebih dahulu.", "error"); return; }
  try {
    await action(auditId);
  } catch (error) {
    toast(error.message || "Permintaan gagal.", "error");
  }
}

function objectionStage() {
  return document.getElementById("objection-stage")?.value || "pre_bid";
}

function objectionFilename() {
  return objectionStage() === "post_award" ? "draf-sanggahan" : "draf-permohonan-penjelasan";
}

async function openObjection() {
  const stageSelect = document.getElementById("objection-stage");
  if (stageSelect) stageSelect.onchange = openObjection;
  await withAudit(async (auditId) => {
    const preview = await api.createSanggahan({ audit_id: auditId, format: "markdown", stage: objectionStage() });
    const textarea = document.getElementById("objection-draft");
    if (textarea) textarea.value = decodeText(preview);
    const meta = document.getElementById("objection-meta");
    if (meta) meta.textContent = `Poin yang dimasukkan server: ${(preview.findings_included || []).join(", ") || "—"}. Rujukan pasal wajib diverifikasi ahli hukum sebelum diajukan.`;
    const dialog = document.getElementById("objection-dialog");
    if (dialog && !dialog.open) dialog.showModal();
  });
}

function downloadObjectionTxt() {
  const text = document.getElementById("objection-draft")?.value || "";
  if (!text) { toast("Tidak ada draf surat.", "error"); return; }
  downloadBlob(new Blob([text], { type: "text/markdown;charset=utf-8" }), `${objectionFilename()}.md`);
  toast("Draf surat .MD berhasil diunduh.");
}

async function downloadObjectionDocx() {
  await withAudit(async (auditId) => {
    const result = await api.createSanggahan({ audit_id: auditId, format: "docx", stage: objectionStage() });
    downloadDocument(result, `${objectionFilename()}.docx`);
    toast(`Draf surat DOCX diunduh (${(result.findings_included || []).length} poin, SHA-256 dicatat di jejak audit).`);
    refreshProofIfOpen(auditId);
  });
}

async function exportMinutesDoc() {
  await withAudit(async (auditId) => {
    const result = await api.createMinutes({ audit_id: auditId, format: "docx" });
    downloadDocument(result, "berita-acara-hasil-evaluasi-draft.docx");
    toast("Draf Berita Acara Hasil Evaluasi (DOCX) diunduh dan dicatat di jejak audit.");
    refreshProofIfOpen(auditId);
  });
}

async function exportClarificationDoc() {
  await withAudit(async (auditId) => {
    const result = await api.createClarification({ audit_id: auditId, format: "docx" });
    downloadDocument(result, "surat-permintaan-klarifikasi.docx");
    toast("Draf surat klarifikasi (DOCX) diunduh.");
    refreshProofIfOpen(auditId);
  });
}

async function exportBoq() {
  await withAudit(async (auditId) => {
    const result = await api.exportBoq(auditId);
    downloadDocument(result, "bidsentry-boq.xlsx");
    toast(result.line_items
      ? `BoQ Excel diunduh: ${result.line_items} baris, ${result.python_mismatches} selisih aritmetika menurut kalkulator Python.`
      : "BoQ Excel diunduh. Tidak ada baris BoQ terstruktur di dokumen; lembar Jejak Hitungan tetap terisi.");
  });
}

async function loadProof(auditId = currentAuditId()) {
  if (!auditId) return;
  setState({ proofLoading: true });
  try {
    const [proof, integrity] = await Promise.all([api.proof(auditId), api.verifyAuditLog().catch(() => null)]);
    setState({ proof, proofIntegrity: integrity, proofLoading: false });
  } catch (error) {
    setState({ proof: null, proofLoading: false });
    toast(error.message || "Jejak audit tidak dapat dimuat.", "error");
  }
}

function refreshProofIfOpen(auditId) {
  if (getState().reviewTab === "proof") loadProof(auditId);
}

async function logout() {
  try { await api.logout(); } catch {}
  auditMemoryCache.clear();
  clearDraftInputs();
  setState({ session: { ...(getState().session || {}), authenticated: false, role: null } });
  resetWorkspaceState();
}

async function login(form) {
  const role = form.dataset.loginRole;
  const pin = form.elements.namedItem("pin")?.value || null;
  const button = form.querySelector("button[type=submit]");
  if (button) button.disabled = true;
  try {
    const session = await api.login(role, pin);
    auditMemoryCache.clear();
    clearDraftInputs();
    resetWorkspaceState();
    setState({ session, sessionChecked: true, roleTransition: session.role });
    setTimeout(() => setState({ roleTransition: null }), 1100);
    toast(`Masuk sebagai ${session.label}.`);
    await loadWorkspace({ preserveSelection: false });
  } catch (error) {
    toast(error.message || "Login gagal.", "error");
  } finally {
    if (button) button.disabled = false;
  }
}

let economicsTimer = null;
async function loadEconomics(auditId = currentAuditId()) {
  if (!auditId) return;
  try {
    const economics = await api.economics(auditId, getState().economicsInputs || {});
    if (currentAuditId() === auditId) setState({ economics });
  } catch {
    setState({ economics: null });
  }
}

function clearDraftInputs() {
  document.getElementById("audit-form")?.reset();
  for (const field of Object.keys(uploadedFiles)) { uploadedFiles[field] = []; uploadErrors[field] = []; }
  clearUploadedFileLabels();
}

// ---------------------------------------------------------------------------
// Demo hotkeys
//   [1] Pokja + Paket A   [2] Vendor + Paket B   [Esc] close dialogs/overlays
// Keys are ignored while typing in a form field or when Ctrl/Alt/Cmd is held.
// ---------------------------------------------------------------------------
let demoPackagesCache = null;
let demoInFlight = false;

async function demoPackages() {
  if (!demoPackagesCache) demoPackagesCache = (await api.demoPackages()).packages || [];
  return demoPackagesCache;
}

async function ensureRole(role) {
  const session = getState().session;
  if (session?.authenticated && session.role === role) return true;
  const roleInfo = (session?.roles || []).find((item) => item.role === role);
  if (roleInfo?.pin_required) {
    toast("Peran ini memerlukan PIN. Masuk lewat layar login terlebih dahulu.", "error");
    return false;
  }
  if (session?.authenticated) {
    try { await api.logout(); } catch {}
  }
  const next = await api.login(role, null);
  auditMemoryCache.clear();
  clearDraftInputs();
  resetWorkspaceState();
  setState({ session: next, sessionChecked: true, roleTransition: role });
  setTimeout(() => setState({ roleTransition: null }), 1100);
  return true;
}

async function runDemo(key) {
  if (demoInFlight) return;
  demoInFlight = true;
  try {
    const pkg = (await demoPackages()).find((item) => item.key === key);
    if (!pkg) { toast(`Paket demo ${key} tidak ditemukan. Jalankan: python scripts/seed_demo.py`, "error"); return; }
    if (!(await ensureRole(pkg.role))) return;
    await loadWorkspace({ preserveSelection: false });
    let row = (getState().audits || []).find((audit) => audit.package_name === pkg.request.package_name);
    if (!row) {
      toast(`Menjalankan ${pkg.title}…`);
      const result = await api.evaluateAudit(pkg.request);
      await loadWorkspace({ preserveSelection: false });
      row = { audit_id: result.audit_id };
    }
    setState({ reviewTab: "matrix", activeView: "review" });
    await selectAudit(row.audit_id);
    setTimeout(() => document.getElementById("risk-review")?.scrollIntoView({ behavior: "smooth", block: "start" }), 150);
    toast(`${pkg.title} siap. ${pkg.story}`);
  } catch (error) {
    toast(error.message || "Demo tidak dapat dimuat.", "error");
  } finally {
    demoInFlight = false;
  }
}

function isTypingTarget(target) {
  if (!target) return false;
  const tag = target.tagName;
  return target.isContentEditable || tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
}

document.addEventListener("keydown", (event) => {
  if (event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey) return;
  if (event.key === "Escape") {
    document.querySelectorAll("dialog[open]").forEach((dialog) => dialog.close());
    setState({ roleTransition: null, expandedFindingId: null });
    return;
  }
  if (isTypingTarget(event.target) || document.querySelector("dialog[open]")) return;
  const key = event.key.toLowerCase();
  if (key === "1" || key === "2") {
    event.preventDefault();
    runDemo(key === "1" ? "A" : "B");
  }
});

async function bootstrap() {
  try {
    const session = await api.me();
    setState({ session, sessionChecked: true });
    if (session?.authenticated) await loadWorkspace();
    else setState({ loading: false });
  } catch (error) {
    setState({ sessionChecked: true, loading: false });
    toast(error.message || "Server tidak dapat dihubungi.", "error");
  }
}

window.addEventListener("bidsentry:auth-required", (event) => {
  if (event.detail?.code === "LOGIN_REQUIRED") {
    setState({ session: { ...(getState().session || {}), authenticated: false, role: null } });
    toast("Sesi berakhir. Silakan masuk kembali sesuai peran.", "error");
  }
});

// Global click event listeners
document.addEventListener("click", async (event) => {
  const toastClose = event.target.closest('[data-action="close-toast"]');
  if (toastClose) {
    toastNode.className = "toast";
    return;
  }

  const dropZone = event.target.closest(".drop-zone");
  if (dropZone) {
    pendingReplace = null;
    document.querySelector(`[data-file-input="${dropZone.dataset.dropTarget}"]`)?.click();
    return;
  }

  const auditRow = event.target.closest(".audit-row");
  if (auditRow && !event.target.closest('[data-action="delete-audit"]')) {
    selectAudit(auditRow.dataset.auditId);
    return;
  }

  const target = event.target.closest("[data-action]");
  if (event.target.closest("#test-integrations")) {
    await testIntegrations();
    return;
  }

  if (!target) return;
  const action = target.dataset.action;

  if (action === "load-sample-tender") loadSampleTender();
  if (action === "new-audit") openAuditDialog();
  if (action === "add-more-docs") openAuditDialog(getState().lastAuditDraft);
  if (action === "open-settings") openSettingsDialog();
  if (action === "close-dialog") document.getElementById("audit-dialog")?.close();
  if (action === "close-utility") target.closest("dialog")?.close();
  if (action === "close-confirm-delete") document.getElementById("confirm-delete-dialog")?.close();
  if (action === "execute-delete-audit") executeDeleteAudit();
  if (action === "refresh") loadWorkspace();
  if (action === "theme-toggle") {
    const theme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem("bidsentry-theme", theme); } catch {}
    render();
  }
  if (action === "logout") { await logout(); return; }
  if (action === "export-boq") exportBoq();
  if (action === "export-clarification") exportClarificationDoc();
  if (action === "open-proof-step") {
    setState({ reviewTab: "proof", proofFocus: target.dataset.stepId });
    await loadProof();
    requestAnimationFrame(() => document.getElementById(`proof-${target.dataset.stepId}`)?.scrollIntoView({ behavior: "smooth", block: "center" }));
    return;
  }
  if (action === "set-summary-tab") {
    const tab = target.dataset.tab || "project";
    setState({ crossSummaryTab: tab });
  }
  if (action === "export") exportData();
  if (action === "export-review") exportReview();
  if (action === "export-selected-review") exportSelectedReview();
  if (action === "export-minutes") exportMinutesDoc();
  if (action === "open-objection") openObjection();
  if (action === "download-objection") downloadObjectionDocx();
  if (action === "download-objection-txt") downloadObjectionTxt();
  if (action === "copy-objection") {
    navigator.clipboard.writeText(document.getElementById("objection-draft")?.value || "").then(
      () => toast("Draf surat disalin ke clipboard."),
      () => toast("Clipboard tidak dapat diakses browser.", "error")
    );
  }
  if (action === "print-objection") window.print();
  if (action === "browse-file") document.querySelector(`[data-file-input="${target.dataset.fileTarget}"]`)?.click();
  if (action === "clear-section") clearSlotSection(target.dataset.field);
  if (action === "remove-file") removeUploadedFile(target.dataset.field, target.dataset.fileId);
  if (action === "dismiss-error") dismissUploadError(target.dataset.field, target.dataset.errorId);

  if (action === "view-overview") { setState({ activeView: "overview" }); document.querySelector(".main-content")?.scrollTo({ top: 0, behavior: "smooth" }); }
  if (action === "focus-audits") { setState({ activeView: "audits" }); document.getElementById("audit-register")?.scrollIntoView({ behavior: "smooth", block: "start" }); }
  if (action === "focus-review") { setState({ activeView: "review" }); document.getElementById("risk-review")?.scrollIntoView({ behavior: "smooth", block: "start" }); }
  if (action === "prev-page") setState({ historyPage: Math.max(1, (getState().historyPage || 1) - 1) });
  if (action === "next-page") setState({ historyPage: (getState().historyPage || 1) + 1 });

  if (action === "review-tab") {
    const tab = ["insights", "proof"].includes(target.dataset.tab) ? target.dataset.tab : "matrix";
    setState({ reviewTab: tab, proofFocus: null, reviewInsightsVisited: getState().reviewInsightsVisited || tab === "insights" });
    if (tab === "proof") loadProof();
  }

  if (action === "delete-audit") {
    event.preventDefault();
    event.stopPropagation();
    deleteAuditRecord(target.dataset.auditId, target.dataset.packageName);
    return;
  }

  if (action === "select-audit" || action === "select-project") {
    selectAudit(target.dataset.auditId);
    if (action === "select-project") {
      const reviewSection = document.getElementById("risk-review") || document.querySelector(".detail-card");
      if (reviewSection) {
        reviewSection.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }
  }
  if (action === "review-filter") setState({ reviewFilter: target.dataset.filter, expandedFindingId: null });
  if (action === "toggle-finding") setState({ expandedFindingId: getState().expandedFindingId === target.dataset.findingId ? null : target.dataset.findingId });

  if (action === "record-review-feedback") {
    target.disabled = true;
    try {
      const feedback = await api.recordFindingReview({
        audit_id: target.dataset.auditId,
        finding_id: target.dataset.findingId,
        outcome: target.dataset.outcome,
      });
      setState({ reviewFeedback: feedback });
      toast(feedback?.reviewed_assessment?.excluded_by_reviewer?.length
        ? `Keputusan reviewer tersimpan. Risiko pasca-review: ${feedback.reviewed_assessment.label} (${feedback.reviewed_assessment.verdict}).`
        : "Keputusan reviewer tersimpan di log audit.");
    } catch (error) {
      target.disabled = false;
      toast(error.message, "error");
    }
  }
});

// Change event listeners for filters & reviewer overrides
document.addEventListener("change", (event) => {
  if (event.target.id === "risk-filter") {
    setState({ riskFilter: event.target.value, historyPage: 1 });
  }
  if (event.target.id === "verdict-filter") {
    setState({ verdictFilter: event.target.value, historyPage: 1 });
  }
});

// Search input with 300ms debounce (Requirement 3.5)
document.addEventListener("input", (event) => {
  const economicsForm = event.target.closest?.("[data-economics-form]");
  if (economicsForm) {
    const values = Object.fromEntries(new FormData(economicsForm).entries());
    setState({ economicsInputs: values }, { notify: false });
    if (economicsTimer) clearTimeout(economicsTimer);
    economicsTimer = setTimeout(() => loadEconomics(), 400);
    return;
  }
  if (event.target.id === "audit-search") {
    const spinner = document.getElementById("search-spinner");
    if (spinner) spinner.hidden = false;
    if (searchDebounceTimer) clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(() => {
      setState({ query: event.target.value, historyPage: 1 });
      const sp = document.getElementById("search-spinner");
      if (sp) sp.hidden = true;
    }, 300);
  }
});

// File input handlers
document.addEventListener("change", async (event) => {
  const picker = event.target.closest?.(".file-picker");
  if (!picker) return;
  const field = picker.dataset.fileInput;
  if (!field) return;
  const files = [...(picker.files || [])];
  if (files.length) await ingestFiles(files, field);
  picker.value = "";
});

// Drag and drop event listeners
["dragenter", "dragover", "dragleave", "drop"].forEach((eventName) => {
  window.addEventListener(eventName, (event) => event.preventDefault(), false);
});

document.addEventListener("dragenter", (event) => {
  const zone = event.target.closest?.(".drop-zone");
  if (!zone) return;
  event.preventDefault();
  event.stopPropagation();
  if (event.dataTransfer) event.dataTransfer.dropEffect = "copy";
  const field = zone.dataset.dropTarget;
  if (!field) return;
  const count = setDragCounter(field, getDragCounter(field) + 1);
  if (count > 0) zone.classList.add("is-dragging");
});

document.addEventListener("dragover", (event) => {
  const zone = event.target.closest?.(".drop-zone");
  if (!zone) return;
  event.preventDefault();
  event.stopPropagation();
  if (event.dataTransfer) event.dataTransfer.dropEffect = "copy";
  zone.classList.add("is-dragging");
});

document.addEventListener("dragleave", (event) => {
  const zone = event.target.closest?.(".drop-zone");
  if (!zone) return;
  event.preventDefault();
  event.stopPropagation();
  const field = zone.dataset.dropTarget;
  if (!field) return;
  const count = setDragCounter(field, getDragCounter(field) - 1);
  if (count <= 0) zone.classList.remove("is-dragging");
});

document.addEventListener("drop", (event) => {
  const zone = event.target.closest?.(".drop-zone");
  if (!zone) return;
  event.preventDefault();
  event.stopPropagation();
  const field = zone.dataset.dropTarget;
  if (!field) return;
  setDragCounter(field, 0);
  zone.classList.remove("is-dragging");
  const files = [...(event.dataTransfer?.files || [])];
  if (files.length) ingestFiles(files, field);
});

// Audit form submission with input preservation and automatic tab switch (Requirements 3.1 & 3.2)
document.addEventListener("submit", async (event) => {
  if (event.target.dataset?.loginRole) {
    event.preventDefault();
    await login(event.target);
    return;
  }
  if (event.target.id === "settings-form") {
    event.preventDefault();
    await saveSettings(event.target);
    return;
  }
  if (event.target.id !== "audit-form") return;
  event.preventDefault();

  if (activeUploads) {
    toast("Tunggu sampai semua file selesai dibaca.", "error");
    return;
  }

  const form = event.target;
  const values = new FormData(form);
  const payload = {
    package_name: String(values.get("package_name") || "").trim() || "Audit dokumen",
    tender_id: String(values.get("tender_id") || "").trim(),
    notice_number: String(values.get("notice_number") || "").trim(),
    pokja_name: String(values.get("pokja_name") || "").trim(),
    company_name: String(values.get("company_name") || "").trim(),
    contract_value_idr: values.get("contract_value_idr") ? Number(values.get("contract_value_idr")) : null,
    dok_pemilihan: String(values.get("dok_pemilihan") || "").trim(),
    adendum: String(values.get("adendum") || "").trim(),
    pustaka: String(values.get("pustaka") || "").trim(),
    contract_draft: String(values.get("contract_draft") || "").trim(),
    baseline_contract: String(values.get("baseline_contract") || "").trim(),
    bid_deadline: String(values.get("bid_deadline") || "").trim() || null,
    review_role: String(values.get("review_role") || "procurement"),
    allow_external_processing: values.get("allow_external_processing") === "on",
  };

  if (!payload.dok_pemilihan && !payload.adendum && !payload.pustaka && !payload.contract_draft && !payload.baseline_contract) {
    toast("Masukkan teks atau unggah minimal satu dokumen.", "error");
    return;
  }

  const submit = document.getElementById("submit-audit");
  if (submit) {
    submit.disabled = true;
    submit.textContent = "Memeriksa dokumen…";
  }

  try {
    const result = await api.evaluateAudit(payload);
    const localRow = {
      ...result,
      tender_id: result.tender_id || result.audit_id.slice(0, 8).toUpperCase(),
      agency: result.pokja_name || "",
      vendor_name: result.company_name || "",
      source: "local_audit_log",
      risk_method: result.risk.method,
      summary: { ...result.summary, findings: result.findings.length },
    };

    document.getElementById("audit-dialog")?.close();

    // Preserve form inputs (Requirement 3.2: DO NOT reset form or wipe files)
    setState({ query: "", riskFilter: "ALL", lastAuditDraft: payload });
    await loadWorkspace({ preserveSelection: false });
    auditMemoryCache.set(result.audit_id, result);

    const otherRows = (getState().audits || []).filter((row) => row.audit_id !== localRow.audit_id);
    setState({
      audits: [localRow, ...otherRows],
      selectedAuditId: localRow.audit_id,
      currentAudit: result,
      customReview: result,
      reviewFilter: "ALL",
      expandedFindingId: null,
      activeView: "review",
      reviewTab: "matrix",
      reviewInsightsVisited: true,
      proof: null,
      economics: null,
    });
    loadEconomics(result.audit_id);

    try {
      setState({ reviewFeedback: await api.reviewFeedback(result.audit_id) });
    } catch {
      setState({ reviewFeedback: null });
    }

    // Automatic smooth scroll to findings (Requirement 3.1)
    setTimeout(() => {
      document.getElementById("risk-review")?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 120);

    toast(`Evaluasi selesai: ${result.executive_summary?.eligibility || result.verdict}.`);
  } catch (error) {
    toast(error.message || "Pemeriksaan gagal dijalankan.", "error");
  } finally {
    const button = document.getElementById("submit-audit");
    if (button && activeUploads === 0) {
      button.disabled = false;
      button.innerHTML = auditSubmitReadyMarkup;
    }
  }
});

bootstrap();
