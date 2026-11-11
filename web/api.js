const API_ROOT = "/api";

let currentAuthToken = "";

export function setAuthToken(token) {
  currentAuthToken = (token || "").trim();
}

export function getAuthToken() {
  return currentAuthToken;
}

async function request(path, options = {}) {
  const timeoutSignal = AbortSignal.timeout(options.timeout ?? 30000);
  const headers = {
    Accept: "application/json",
    ...(options.body ? { "Content-Type": "application/json" } : {}),
    ...(currentAuthToken ? { Authorization: `Bearer ${currentAuthToken}` } : {}),
    ...options.headers,
  };
  try {
    const response = await fetch(`${API_ROOT}${path}`, {
      ...options,
      credentials: "same-origin",
      signal: options.signal ? AbortSignal.any([options.signal, timeoutSignal]) : timeoutSignal,
      headers,
    });
    const body = await response.json().catch(() => null);
    if (response.status === 401 && typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("bidsentry:auth-required", { detail: { path, code: body?.error?.code } }));
    }
    if (!response.ok) {
      const error = new Error(body?.error?.message || `Permintaan gagal (${response.status}).`);
      error.code = body?.error?.code;
      error.status = response.status;
      throw error;
    }
    return body?.data;
  } catch (error) {
    if (error.name === "AbortError" || error.name === "TimeoutError") throw new Error("Waktu tunggu habis. Periksa koneksi server.");
    throw error;
  }
}

const post = (path, input, timeout = 60000) => request(path, { method: "POST", body: JSON.stringify(input ?? {}), timeout });

export const api = {
  // Session / role
  me: () => request("/auth/me"),
  login: (role, pin) => post("/auth/login", { role, pin }, 15000),
  logout: () => post("/auth/logout", {}, 15000),

  health: () => request("/health"),
  overview: () => request("/overview"),
  decisionTable: () => request("/risk/decision-table"),
  audits: ({ q = "", risk = "ALL" } = {}) => request(`/audits?${new URLSearchParams({ q, risk })}`),
  getAudit: (auditId) => request(`/audits/${encodeURIComponent(auditId)}`),
  proof: (auditId) => request(`/audits/${encodeURIComponent(auditId)}/proof`),
  economics: (auditId, params = {}) => request(`/audits/${encodeURIComponent(auditId)}/economics?${new URLSearchParams(Object.fromEntries(Object.entries(params).filter(([, value]) => value !== "" && value != null)))}`),
  benchmarkSummary: () => request("/benchmark/summary"),
  demoPackages: () => request("/demo/packages"),
  deleteAudit: (auditId) => request(`/audits?${new URLSearchParams({ audit_id: auditId })}`, { method: "DELETE" }),
  evaluateAudit: (input) => post("/v1/audit/evaluate", input),

  // Role-specific documents (enforced server-side)
  createSanggahan: (input) => post("/v1/audit/sanggahan-doc", input),        // Vendor
  verifyAuditLog: () => request("/audit-log/verify"),
  createMinutes: (input) => post("/v1/audit/minutes-eval-doc", input),       // Pokja
  createClarification: (input) => post("/v1/audit/clarification-doc", input), // Pokja
  exportBoq: (auditId) => post("/export/boq", { audit_id: auditId }),
  exportWorkbook: (input) => post("/export/workbook", input),

  reviewFeedback: (auditId = "") => request(`/review-feedback${auditId ? `?${new URLSearchParams({ audit_id: auditId })}` : ""}`),
  recordFindingReview: (input) => post("/review-feedback", input, 30000),
  extractDocument: (file) => request(`/documents/extract?${new URLSearchParams({ filename: file.name })}`, {
    method: "POST", body: file, headers: { "Content-Type": "application/octet-stream" }, timeout: 60000,
  }),
  dispatch: (input) => post("/dispatch", input),
  integrationSettings: () => request("/settings/integrations"),
  testIntegrations: () => request("/settings/integrations/test", { timeout: 60000 }),
  saveIntegrationSettings: (input) => request("/settings/integrations", { method: "PUT", body: JSON.stringify(input) }),
};

/** Decode a `{filename, content_type, content_base64}` API document and save it. */
export function downloadDocument(result, fallbackName = "dokumen") {
  const bytes = Uint8Array.from(atob(result?.content_base64 || ""), (char) => char.charCodeAt(0));
  const blob = new Blob([bytes], { type: result?.content_type || "application/octet-stream" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = result?.filename || fallbackName;
  anchor.click();
  requestAnimationFrame(() => URL.revokeObjectURL(url));
}

export function decodeText(result) {
  const bytes = Uint8Array.from(atob(result?.content_base64 || ""), (char) => char.charCodeAt(0));
  return new TextDecoder("utf-8").decode(bytes);
}
