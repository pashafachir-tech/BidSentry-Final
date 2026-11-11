const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
const number = (value) => new Intl.NumberFormat("id-ID").format(Number(value || 0));
const rupiah = (value) => `Rp ${number(Math.round(Number(value || 0)))}`;

export const RISK_META = {
  NOT_ASSESSABLE: { label: "Tidak Dapat Dinilai", css: "risk-na", hint: "Dokumen tidak memuat persyaratan yang dikenali. Ini bukan tanda aman." },
  LOW: { label: "Rendah", css: "risk-low", hint: "Persyaratan yang terbaca terpenuhi." },
  MEDIUM: { label: "Sedang", css: "risk-medium", hint: "Ada bukti yang belum lengkap atau kesenjangan berkeparahan sedang." },
  HIGH: { label: "Tinggi", css: "risk-high", hint: "Ada kesenjangan berkeparahan tinggi yang terkonfirmasi teks." },
  CRITICAL: { label: "Kritis", css: "risk-critical", hint: "Ada kesenjangan pada aturan berdampak kritis atau akumulasi kesenjangan tinggi." },
};
const statusLabels = { TERPENUHI: "Terpenuhi", GAP: "Kesenjangan", EXPIRING: "Segera berakhir", SUPERSEDED: "Diubah adendum", REVIEW: "Perlu diperiksa" };
const statusClasses = { TERPENUHI: "status-ok", GAP: "status-gap", EXPIRING: "status-warn", SUPERSEDED: "status-muted", REVIEW: "status-warn" };
const LEGAL_STATUS = {
  DIPERIKSA_NASKAH: { label: "Dicocokkan dengan naskah", css: "tag-reviewed" },
  DIPERIKSA_SEKUNDER: { label: "Sumber sekunder; cek naskah resmi", css: "tag-homework" },
  PERLU_VERIFIKASI_HUKUM: { label: "Perlu verifikasi hukum", css: "tag-legal" },
};
const OUTCOMES = [["SUPPORTED", "Didukung bukti"], ["NEEDS_MORE_INFO", "Perlu klarifikasi"], ["NOT_SUPPORTED", "Tidak didukung (false positive)"]];
const KIND_LABELS = {
  input: "Dokumen masuk", pii_redaction: "Redaksi PII", ai_call: "Panggilan AI", ai_validation: "Validasi kutipan AI",
  calculation: "Kalkulasi Python", decision: "Keputusan risiko", document: "Dokumen dihasilkan", guardrail: "Guardrail",
};

export function riskBadge(level, { large = false } = {}) {
  const meta = RISK_META[level] || RISK_META.NOT_ASSESSABLE;
  return `<span class="risk-badge ${meta.css} ${large ? "risk-badge-large" : ""}" title="${escapeHtml(meta.hint)}"><i aria-hidden="true"></i>Risiko ${escapeHtml(meta.label)}</span>`;
}

function buildReview(state) {
  const result = state.currentAudit || state.customReview || (state.audits && state.audits.find((row) => row.audit_id === state.selectedAuditId)) || (state.audits && state.audits[0]) || null;
  if (!result) return { isCustom: false, findings: [], package_name: "Belum ada evaluasi", verdict: "—", risk_level: "NOT_ASSESSABLE", summary: "Masukkan dokumen tender dan bukti penyedia untuk memulai pemeriksaan." };

  const feedback = state.reviewFeedback?.audit_id === result.audit_id ? state.reviewFeedback : null;
  const outcomes = feedback?.outcomes || {};
  const findings = (result.findings || []).map((finding) => {
    const outcome = outcomes[finding.id]?.outcome;
    return outcome ? { ...finding, reviewer_outcome: outcome } : finding;
  });
  const reviewed = feedback?.reviewed_assessment;
  const excluded = reviewed?.excluded_by_reviewer || [];
  const risk = reviewed && excluded.length ? reviewed : (result.risk || {});
  return {
    ...result,
    id: result.audit_id || "latest",
    package_name: result.package_name || "Evaluasi dokumen",
    verdict: reviewed && excluded.length ? reviewed.verdict : (result.executive_summary?.eligibility || result.verdict || "—"),
    system_verdict: result.executive_summary?.eligibility || result.verdict,
    reviewed_by_human: Boolean(reviewed && excluded.length),
    summary: result.executive_summary?.executive_summary || result.review_recommendation || "Periksa setiap temuan terhadap dokumen sumber.",
    findings,
    risk,
    risk_level: risk.level || result.risk_level || "NOT_ASSESSABLE",
    coverage: result.coverage || null,
    isCustom: true,
  };
}

export function getReviewSnapshot(state) { return buildReview(state); }

function findingMatches(status, filter) {
  if (filter === "ALL") return true;
  if (filter === "NEEDS_REVIEW") return ["GAP", "EXPIRING", "REVIEW"].includes(status);
  return status === filter;
}

function renderFinding(row, state, review, role) {
  const expanded = state.expandedFindingId === row.id;
  const status = String(row.status || "REVIEW").toUpperCase();
  const outcome = row.reviewer_outcome;
  const outcomeLabel = OUTCOMES.find(([value]) => value === outcome)?.[1];
  const tags = [
    row.origin === "ai_extraction_python_validated" ? '<span class="tag tag-ai">Diekstrak AI · divalidasi Python</span>' : "",
    row.origin === "ai_extraction_unconfirmed" ? '<span class="tag tag-ai">Kandidat AI · cek manual · tidak memengaruhi verdict</span>' : "",
    row.threshold_unverified ? '<span class="tag tag-homework">Ambang belum terverifikasi</span>' : "",
    role === "vendor" && row.objectionable ? '<span class="tag tag-objection">Dapat dipersoalkan</span>' : "",
    role === "vendor" && row.party === "bidder_evidence" && status !== "TERPENUHI" ? '<span class="tag tag-homework">Lengkapi berkas Anda</span>' : "",
    outcomeLabel ? `<span class="tag ${outcome === "NOT_SUPPORTED" ? "tag-ignored" : "tag-reviewed"}">Reviewer: ${escapeHtml(outcomeLabel)}</span>` : "",
  ].join("");
  return `
    <tr class="review-row ${expanded ? "review-row-open" : ""} ${outcome === "NOT_SUPPORTED" ? "is-dismissed" : ""}" data-action="toggle-finding" data-finding-id="${escapeHtml(row.id)}" tabindex="0" aria-expanded="${expanded}">
      <td><strong>${escapeHtml(row.id || "TEMUAN")}</strong><small>${escapeHtml(row.category || "Pemeriksaan")}</small></td>
      <td><strong>${escapeHtml(row.clause || row.category || "Temuan")}</strong><small>Sumber: ${escapeHtml(row.source || "Lokator belum tersedia")}</small><div class="tag-row">${tags}</div></td>
      <td><span class="status-pill ${statusClasses[status] || "status-muted"}">${escapeHtml(statusLabels[status] || status)}</span></td>
      <td><span>${escapeHtml(row.evidence || "Tidak ada bukti teks yang cocok. Periksa dokumen sumber.")}</span>${row.evidence_source ? `<small class="evidence-source">Bukti: ${escapeHtml(row.evidence_source)}</small>` : ""}</td>
    </tr>
    ${expanded ? `
      <tr class="review-expanded">
        <td colspan="4">
          <div class="review-expanded-content">
            ${row.requirement_evidence ? `<p><strong>Kutipan ketentuan (verbatim):</strong> ${escapeHtml(row.requirement_evidence)}</p>` : ""}
            <p><strong>Catatan pemeriksaan:</strong> ${escapeHtml(row.review_note || "Cocokkan fakta dan kutipan dengan dokumen resmi.")}</p>
            ${(row.legal_basis || []).length ? `<div class="legal-ref"><strong>Dasar hukum:</strong><ul>${row.legal_basis.map((citation) => `<li><b>${escapeHtml(citation.formal)}</b> — ${escapeHtml(citation.substance)} <span class="tag ${LEGAL_STATUS[citation.status]?.css || "tag-legal"}" title="${escapeHtml(citation.source || "")}">${escapeHtml(LEGAL_STATUS[citation.status]?.label || "Perlu verifikasi hukum")}</span></li>`).join("")}</ul></div>`
              : row.legal_reference ? `<p class="legal-ref"><strong>Rujukan kandidat:</strong> ${escapeHtml(row.legal_reference)} <span class="tag tag-legal">Perlu verifikasi hukum</span></p>` : ""}
            ${row.calculation_ref ? `<p><button type="button" class="button button-quiet button-small" data-action="open-proof-step" data-step-id="${escapeHtml(row.calculation_ref)}">Lihat hitungan Python (${escapeHtml(row.calculation_ref)})</button></p>` : ""}
            ${review.audit_id ? `
              <div class="reviewer-feedback">
                <strong>Keputusan reviewer manusia (tersimpan di log audit):</strong>
                <div class="reviewer-feedback-actions">
                  ${OUTCOMES.map(([value, label]) => `<button type="button" class="review-feedback-button ${outcome === value ? "is-selected" : ""}" data-action="record-review-feedback" data-audit-id="${escapeHtml(review.audit_id)}" data-finding-id="${escapeHtml(row.id)}" data-outcome="${value}">${label}</button>`).join("")}
                </div>
                <small>Temuan "tidak didukung" dikeluarkan dari perhitungan risiko pasca-review, BA, dan sanggahan.</small>
              </div>` : ""}
          </div>
        </td>
      </tr>` : ""}`;
}

function renderAdendum(result) {
  const diff = result.adendum_reconciliation;
  if (!diff || diff.status !== "compared") return "";
  const rows = (diff.changes || []).map((item) => `<tr><td>${escapeHtml(item.item_id)}</td><td>${escapeHtml(item.change_status)}</td><td>${escapeHtml(item.original_requirement || "—")}</td><td>${escapeHtml(item.adendum_requirement || "—")}</td></tr>`).join("");
  return `<article class="review-tool-card"><p class="eyebrow">REKONSILIASI ADENDUM</p><h3>Perubahan persyaratan</h3><p>${escapeHtml(diff.review_note || "Perubahan teks perlu diperiksa.")}</p><div class="review-table-wrap"><table class="review-table"><thead><tr><th>ID</th><th>STATUS</th><th>TEKS ASLI</th><th>TEKS ADENDUM</th></tr></thead><tbody>${rows || '<tr><td colspan="4">Tidak ada perubahan teks yang terdeteksi.</td></tr>'}</tbody></table></div></article>`;
}

function renderPenalty(penalty) {
  if (!penalty || penalty.status === "contract_value_required") return "";
  const rows = (penalty.scenarios || []).map((item) => `<tr><td>${number(item.delay_days)} hari</td><td>${rupiah(item.contract_clause_amount_idr)}</td><td>${rupiah(item["1_per_mille_daily_comparison_idr"])}</td><td>${rupiah(item.illustrative_5_percent_cap_amount_idr)}</td></tr>`).join("");
  const uncapped = (penalty.alerts || []).includes("CRITICAL_POISON_PILL");
  const warning = uncapped ? "Klausul denda tanpa batas maksimum terdeteksi. Minta penelaahan sebelum penawaran." : "Perhitungan mengikuti teks klausul yang terbaca.";
  return `<article class="review-tool-card"><p class="eyebrow">KALKULATOR PYTHON · DENDA KETERLAMBATAN</p><h3>Simulasi denda keterlambatan</h3><p class="formula">denda = nilai kontrak × tarif harian × hari terlambat</p><p class="${uncapped ? "penalty-warning" : "penalty-note"}" role="status">${escapeHtml(warning)}</p>${penalty.clause_quote ? `<blockquote>${escapeHtml(penalty.clause_quote)}</blockquote>` : ""}<div class="review-table-wrap"><table class="review-table"><thead><tr><th>TERLAMBAT</th><th>MENURUT KLAUSUL</th><th>PEMBANDING 1‰/HARI</th><th>ILUSTRASI BATAS 5%</th></tr></thead><tbody>${rows}</tbody></table></div><p class="card-footnote">Batas 5% adalah asumsi simulasi, bukan batas maksimum umum dalam Perpres. Verifikasi nilai dasar dan klausul kontrak.</p></article>`;
}

function renderContextual(data) {
  if (!data || data.status !== "success") return `<div class="insights-unavailable"><strong>Ekstraksi AI tidak dijalankan</strong><p>${escapeHtml(data?.message || (data?.status === "not_requested" ? "Aktifkan persetujuan jika kebijakan organisasi mengizinkan pengiriman teks ke AI." : "Periksa konfigurasi provider. Pemeriksaan lokal tetap tersedia."))}</p></div>`;
  const items = data.items || [];
  const validationLabel = { confirmed: "Dikonfirmasi Python → temuan", corroborated: "Sama dengan temuan lokal", not_confirmed: "Tidak lolos validasi Python", context_only: "Konteks saja", needs_human_review: "Perlu dicek manusia" };
  const categoryLabel = { brand_lockin_signals: "Penyebutan merek", timeline_anomalies: "Jadwal", addendum_changes: "Perubahan adendum", personnel_qualifications: "Kualifikasi personel", sla_uptime: "SLA / uptime" };
  return `<div class="insight-card"><div class="insight-card-heading"><div><p class="eyebrow">EKSTRAKSI AI · ${escapeHtml(data.provider || "provider")} ${data.model_id ? `· ${escapeHtml(data.model_id)}` : ""}</p><h3>${escapeHtml(data.scope || "Kutipan yang diekstrak model")}</h3></div><span class="insight-status is-ready">${number(items.length)} KUTIPAN DIVERIFIKASI · ${number(data.rejected_quotes_count || 0)} DITOLAK</span></div>${items.length ? `<ul class="next-action-list">${items.map((item) => `<li><div><strong>${escapeHtml(categoryLabel[item.category] || item.category)}</strong> <span class="tag ${item.validation?.status === "confirmed" ? "tag-ai" : "tag-muted"}">${escapeHtml(validationLabel[item.validation?.status] || "—")}</span><blockquote>${escapeHtml(item.quote)}</blockquote><small>${escapeHtml(item.source)}</small><p>${escapeHtml(item.validation?.detail || item.summary)}</p></div></li>`).join("")}</ul>` : `<p>Tidak ada kutipan yang cocok dengan teks dokumen.</p>`}<p class="insight-footnote">Model hanya mengekstrak kutipan. Setiap kutipan dicocokkan dengan dokumen (beda spasi dan pergantian baris diabaikan) dan disimpan persis seperti teks sumber, lalu divalidasi ulang oleh aturan Python sebelum boleh memengaruhi verdict.</p></div>`;
}

const KEY_LABELS = {
  characters: "jumlah karakter", sha256: "sidik jari SHA-256", requirement_sentences: "kalimat persyaratan", evidence_sentences: "kalimat bukti",
  reference_date: "tanggal acuan", rule: "aturan", digit_count: "jumlah digit", valid_format: "format sah", status: "status",
  contract_value_idr: "nilai kontrak", clause_quote: "kutipan klausul", contract_daily_rate: "tarif denda harian", clause_cap_percentage: "batas denda di klausul",
  uncapped_clause_detected: "denda tanpa batas", alerts: "peringatan", scenarios: "skenario", total_boq_idr: "total BoQ/HPS", pagu_idr: "pagu anggaran",
  boq_quote: "kutipan BoQ/HPS", pagu_quote: "kutipan pagu", deficit_idr: "defisit", deficit_percent: "defisit (%)", bid_preparation_days: "hari penyusunan penawaran",
  objection_days: "hari masa sanggah", thresholds: "ambang", issues: "masalah", required_idr: "nilai disyaratkan", offered_idr: "nilai ditawarkan", shortfall_idr: "kekurangan",
  required_days: "hari disyaratkan", offered_days: "hari ditawarkan", expiry_date: "tanggal kedaluwarsa", bid_deadline: "batas penawaran", remaining_days: "sisa hari",
  requirements_recognized: "persyaratan dikenali", finding_counts: "jumlah temuan", risk_level: "tingkat risiko", verdict: "verdict", drivers: "pemicu",
  prompt_sha256: "sidik jari prompt", prompt_characters: "ukuran prompt", endpoint: "endpoint", provider: "provider", model_id: "model", input_tokens: "token masuk",
  output_tokens: "token keluar", response_sha256: "sidik jari respons", error_type: "jenis galat", redacted_tokens: "data pribadi disamarkan",
  unmasked_pii_detected_in_payload: "PII lolos ke payload", payload_sha256: "sidik jari payload", payload_characters: "ukuran payload", documents: "dokumen",
  quotes_returned: "kutipan dikembalikan", accepted: "diterima", rejected_not_in_source: "ditolak (tidak ada di sumber)", candidates: "kandidat",
  confirmed_new_findings: "temuan baru terkonfirmasi", corroborated: "menguatkan temuan lokal", not_confirmed: "tidak terkonfirmasi",
  quote: "kutipan", days: "hari", threshold: "ambang", confirmed: "terkonfirmasi", rates_idr: "tarif", max_idr: "batas atas", roles_above_max: "posisi di atas batas",
  explicit_markup_statement: "pernyataan mark-up", license_idr: "pos lisensi", maintenance_idr: "pos pemeliharaan", overlap_statement: "pernyataan tumpang tindih",
  potential_overlap_idr: "potensi tumpang tindih", stated_days: "durasi tertulis", threshold_days: "ambang hari", flagged: "ditandai", dok_pemilihan: "dokumen pemilihan",
  adendum: "adendum", pustaka: "bukti penyedia", contract_draft: "draf kontrak", temuan_dimasukkan: "temuan dimasukkan", dibuat: "dibuat",
};
const shortHash = (value) => (typeof value === "string" && /^[0-9a-f]{64}$/.test(value) ? `${value.slice(0, 10)}…${value.slice(-6)}` : value);

function formatValue(value, key = "") {
  if (/_idr$/.test(key) && typeof value === "number") return rupiah(value);
  if (key.includes("sha256")) return shortHash(value) ?? "—";
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "number") return Number.isInteger(value) && Math.abs(value) >= 1000 ? number(value) : String(value);
  if (typeof value === "boolean") return value ? "ya" : "tidak";
  if (Array.isArray(value)) return value.length ? value.map((item) => formatValue(item)).join(", ") : "—";
  if (typeof value === "object") return Object.entries(value).map(([itemKey, item]) => `${KEY_LABELS[itemKey] || itemKey}: ${formatValue(item, itemKey)}`).join(" · ");
  return String(value);
}

function renderKeyValues(object) {
  const entries = Object.entries(object || {});
  if (!entries.length) return "";
  return `<dl class="proof-kv">${entries.map(([key, value]) => `<div><dt>${escapeHtml(KEY_LABELS[key] || key.replaceAll("_", " "))}</dt><dd title="${escapeHtml(typeof value === "string" ? value : "")}">${escapeHtml(formatValue(value, key))}</dd></div>`).join("")}</dl>`;
}

const PIPELINE = [
  { kinds: ["input"], title: "Dokumen", caption: "Diunggah & di-hash SHA-256", icon: "1" },
  { kinds: ["pii_redaction"], title: "Redaksi PII", caption: "NIK, NPWP, rekening, kontak", icon: "2" },
  { kinds: ["ai_call"], title: "Ekstraksi AI", caption: "IBM watsonx.ai / Langflow (opsional)", icon: "3" },
  { kinds: ["ai_validation"], title: "Validasi kutipan", caption: "Teks verbatim sumber + aturan Python", icon: "4" },
  { kinds: ["calculation"], title: "Kalkulasi Python", caption: "Rumus deterministik", icon: "5" },
  { kinds: ["decision"], title: "Tabel keputusan", caption: "Aturan R0–R6", icon: "6" },
  { kinds: ["document"], title: "Dokumen hasil", caption: "DOCX/XLSX + SHA-256", icon: "7" },
];

function renderPipeline(steps, documents, review) {
  const aiSkipped = steps.some((step) => step.kind === "ai_call" && step.status === "skipped");
  return `<ol class="proof-pipeline" aria-label="Alur bukti audit">${PIPELINE.map((stage) => {
    const matched = steps.filter((step) => stage.kinds.includes(step.kind));
    const count = stage.kinds.includes("document") ? documents.length : matched.length;
    const failed = matched.some((step) => step.status === "failed");
    const skipped = count > 0 && matched.length > 0 && matched.every((step) => step.status === "skipped");
    const notNeeded = !count && aiSkipped && (stage.kinds.includes("pii_redaction") || stage.kinds.includes("ai_validation"));
    if (notNeeded) {
      return `<li class="pipe-stage pipe-skipped"><button type="button" disabled><span class="pipe-num">${stage.icon}</span><strong>${stage.title}</strong><small>${stage.caption}</small><em>Tidak diperlukan: tidak ada teks dikirim ke AI</em></button></li>`;
    }
    const state = failed ? "failed" : skipped ? "skipped" : count ? "ok" : "idle";
    const detail = stage.kinds.includes("decision") ? `${review.risk?.rule_applied || "—"} → ${review.risk?.label || "—"}`
      : stage.kinds.includes("ai_call") ? (skipped ? "Tidak dijalankan" : failed ? "Gagal → fallback lokal" : count ? (matched[0]?.outputs?.model_id || matched[0]?.outputs?.provider || "Berhasil") : "Tidak dijalankan")
      : stage.kinds.includes("calculation") ? `${count} hitungan`
      : stage.kinds.includes("document") ? (count ? `${count} diunduh` : "Belum ada")
      : count ? "Selesai" : "—";
    const first = matched[0]?.step_id;
    return `<li class="pipe-stage pipe-${state}"><button type="button" ${first ? `data-action="open-proof-step" data-step-id="${escapeHtml(first)}"` : "disabled"}><span class="pipe-num">${stage.icon}</span><strong>${stage.title}</strong><small>${stage.caption}</small><em>${escapeHtml(detail)}</em></button></li>`;
  }).join("")}</ol>`;
}

function renderIntegrity(integrity) {
  if (!integrity) return "";
  const css = integrity.valid ? "integrity-ok" : "integrity-alarm";
  const label = integrity.valid
    ? `Rantai audit log utuh: ${number(integrity.records)} catatan${integrity.sealed ? " bersegel HMAC" : ""}`
    : "Peringatan integritas: audit log tidak lolos verifikasi";
  return `<p class="integrity-banner ${css}" role="status">${escapeHtml(label)}${integrity.valid ? "" : ` · ${escapeHtml(integrity.message)}. Log dari sebelum penyegelan juga muncul di sini; jalankan scripts/seed_demo.py untuk memulai log baru.`}</p>`;
}

export function renderProof(state, review) {
  if (state.proofLoading) return '<div class="proof-empty">Memuat jejak audit…</div>';
  const proof = state.proof && state.proof.audit_id === review.audit_id ? state.proof : null;
  const steps = proof?.steps || review.proof_log || [];
  if (!steps.length) return '<div class="proof-empty"><strong>Jejak audit belum tersedia untuk audit ini.</strong><p>Audit lama (sebelum pembaruan) tidak menyimpan jejak. Jalankan ulang evaluasi.</p></div>';
  const summary = proof?.summary || review.proof_summary || {};
  const table = proof?.decision_table || [];
  const ai = proof?.ai_governance || review.ai_governance_metadata || {};
  const documents = proof?.documents || review.documents || [];
  const focus = state.proofFocus;
  return `
    ${renderPipeline(steps, documents, review)}
    ${renderIntegrity(state.proofIntegrity)}
    <div class="proof-header">
      <div class="proof-stats">
        <div><span>Langkah tercatat</span><strong>${number(summary.steps || steps.length)}</strong></div>
        <div><span>Panggilan AI berhasil</span><strong>${number(summary.ai_calls || 0)}</strong><small>${escapeHtml((summary.ai_providers || []).join(", ") || "tidak ada")}</small></div>
        <div><span>Kalkulasi Python</span><strong>${number(summary.python_calculations || 0)}</strong></div>
        <div><span>Provider yang benar-benar dipakai</span><strong>${escapeHtml(ai.provider_used || "Tidak ada (aturan lokal)")}</strong><small>${escapeHtml(ai.model_used || ai.role_of_ai || "")}</small></div>
      </div>
      <p class="proof-lede">Urutan bukti: <b>dokumen</b> → <b>redaksi PII</b> → <b>ekstraksi AI (opsional)</b> → <b>validasi kutipan</b> → <b>kalkulasi Python</b> → <b>tabel keputusan</b> → <b>dokumen hasil</b>. Teks dokumen tidak disimpan di jejak ini; hanya hash, angka, dan kutipan pendek.</p>
    </div>
    <ol class="proof-timeline">
      ${steps.map((step) => `
        <li id="proof-${escapeHtml(step.step_id)}" class="proof-step proof-${escapeHtml(step.kind)} proof-status-${escapeHtml(step.status)} ${focus === step.step_id ? "is-focused" : ""}">
          <div class="proof-step-head">
            <span class="proof-id">${escapeHtml(step.step_id)}</span>
            <span class="proof-kind">${escapeHtml(KIND_LABELS[step.kind] || step.kind)}</span>
            <strong>${escapeHtml(step.title)}</strong>
            <span class="proof-actor">${escapeHtml(step.actor)}</span>
            ${step.duration_ms != null ? `<span class="proof-time">${number(step.duration_ms)} ms</span>` : ""}
            <span class="proof-status">${escapeHtml({ ok: "OK", skipped: "Dilewati", failed: "Gagal", rejected: "Ada yang ditolak" }[step.status] || step.status)}</span>
          </div>
          ${step.formula ? `<p class="formula">${escapeHtml(step.formula)}</p>` : ""}
          <div class="proof-io">
            ${Object.keys(step.inputs || {}).length ? `<div><h4>Input</h4>${renderKeyValues(step.inputs)}</div>` : ""}
            ${Object.keys(step.outputs || {}).length ? `<div><h4>Output</h4>${renderKeyValues(step.outputs)}</div>` : ""}
          </div>
          ${step.note ? `<p class="proof-note">${escapeHtml(step.note)}</p>` : ""}
        </li>`).join("")}
      ${documents.map((doc) => `
        <li class="proof-step proof-document">
          <div class="proof-step-head"><span class="proof-id">DOC</span><span class="proof-kind">Dokumen dihasilkan</span><strong>${escapeHtml(doc.filename)}</strong><span class="proof-actor">peran: ${escapeHtml(doc.role || "—")}</span><span class="proof-status">OK</span></div>
          ${renderKeyValues({ sha256: doc.sha256, temuan_dimasukkan: doc.findings_included, dibuat: doc.created_at })}
        </li>`).join("")}
    </ol>
    ${table.length ? `<article class="review-tool-card"><p class="eyebrow">TABEL KEPUTUSAN RISIKO (DETERMINISTIK)</p><h3>Aturan yang dipakai: ${escapeHtml(review.risk?.rule_applied || "—")}</h3><table class="review-table decision-table"><thead><tr><th>ATURAN</th><th>KONDISI</th><th>TINGKAT</th></tr></thead><tbody>${table.map((rule) => `<tr class="${rule.rule === review.risk?.rule_applied ? "is-applied" : ""}"><td>${escapeHtml(rule.rule)}</td><td>${escapeHtml(rule.condition)}</td><td>${riskBadge(rule.level)}</td></tr>`).join("")}</tbody></table></article>` : ""}`;
}

export function engineModeBadge(mode) {
  if (!mode) return "";
  const css = { ai_assisted: "mode-ai", local_fallback: "mode-fallback", local_only: "mode-local" }[mode.mode] || "mode-local";
  return `<span class="engine-mode ${css}" title="${escapeHtml(mode.reason || "")}"><i aria-hidden="true"></i>${escapeHtml(mode.label)}</span>`;
}

function renderEconomics(state, review) {
  const data = state.economics && state.economics.audit_id === review.audit_id ? state.economics : null;
  const inputs = state.economicsInputs || {};
  if (!review.isCustom) return "";
  if (!data) return '<article class="economics-card"><p class="eyebrow">UNIT ECONOMICS PAKET INI</p><p class="muted">Menghitung biaya inferensi dari token audit…</p></article>';
  const a = data.assumptions;
  const machine = data.machine_seconds < 1 ? `${Math.round(data.machine_seconds * 1000)} ms` : `${data.machine_seconds.toLocaleString("id-ID", { maximumFractionDigits: 1 })} detik`;
  return `<article class="economics-card" aria-label="Unit economics">
    <div class="economics-head"><div><p class="eyebrow">UNIT ECONOMICS PAKET INI</p><h3>Biaya mesin vs biaya telaah manual</h3></div><span class="tag ${data.tokens.basis === "measured" ? "tag-reviewed" : "tag-homework"}">${data.tokens.basis === "measured" ? "Token terukur" : "Token diestimasi"}</span></div>
    <div class="economics-grid">
      <div class="econ-tile econ-machine"><span>Biaya inferensi AI / dokumen</span><strong>${rupiah(data.inference_cost_idr)}</strong><small>${number(data.tokens.input)} token masuk · ${number(data.tokens.output)} token keluar</small></div>
      <div class="econ-tile econ-machine"><span>Waktu mesin</span><strong>${machine}</strong><small>aturan Python${data.tokens.ai_calls ? " + panggilan AI" : ""}; belum termasuk waktu verifikasi manusia</small></div>
      <div class="econ-tile econ-human"><span>Telaah manual (asumsi)</span><strong>${rupiah(data.manual_review_cost_idr)}</strong><small>${number(a.manual_review_hours_per_package)} jam × ${rupiah(a.manual_hourly_cost_idr)}</small></div>
      <div class="econ-tile econ-year"><span>Proyeksi ${number(a.packages_per_year)} paket / tahun</span><strong>${rupiah(data.annual.inference_cost_idr)}</strong><small>biaya AI vs ${rupiah(data.annual.manual_review_cost_idr)} telaah manual</small></div>
    </div>
    <form class="economics-inputs" data-economics-form>
      <label>Jam telaah manual / paket<input id="econ-manual-hours" type="number" min="0" max="200" step="0.5" name="manual_hours" value="${escapeHtml(inputs.manual_hours ?? a.manual_review_hours_per_package)}" /></label>
      <label>Biaya per jam (Rp)<input id="econ-hourly-cost" type="number" min="0" step="5000" name="hourly_cost_idr" value="${escapeHtml(inputs.hourly_cost_idr ?? a.manual_hourly_cost_idr)}" /></label>
      <label>Paket per tahun<input id="econ-packages" type="number" min="1" step="100" name="packages_per_year" value="${escapeHtml(inputs.packages_per_year ?? a.packages_per_year)}" /></label>
    </form>
    <p class="econ-caveat">${escapeHtml(data.caveat)} Harga: USD ${a.price_usd_per_1m_input_tokens}/1 juta token masuk, USD ${a.price_usd_per_1m_output_tokens}/1 juta token keluar, kurs Rp ${number(a.usd_idr_rate)}. ${escapeHtml(a.price_source)}</p>
  </article>`;
}

function roleActions(review, role, hasSource) {
  if (!review.isCustom) return '<button class="button button-primary" data-action="new-audit">Mulai pemeriksaan</button>';
  const boq = '<button class="button button-secondary" data-action="export-boq">Unduh BoQ (.xlsx)</button>';
  if (role === "pokja") {
    return `
      <button class="button button-primary" data-action="export-minutes">Draf Berita Acara (.docx)</button>
      <button class="button button-secondary" data-action="export-clarification">Surat klarifikasi ke penyedia (.docx)</button>
      ${boq}`;
  }
  const objectionable = (review.findings || []).filter((item) => item.objectionable && item.reviewer_outcome !== "NOT_SUPPORTED").length;
  return `
    <button class="button button-primary" data-action="open-objection" ${!hasSource || !objectionable ? "disabled" : ""} title="${objectionable ? "" : "Tidak ada kesenjangan dokumen tender yang dapat dipersoalkan"}">Draf surat ke Pokja (.docx) · ${number(objectionable)} poin</button>
    ${boq}`;
}

export function renderReview(state) {
  const role = state.session?.role || "pokja";
  const review = buildReview(state);
  const findings = review.findings || [];
  const filter = state.reviewFilter || "ALL";
  const visible = findings.filter((row) => findingMatches(String(row.status || "REVIEW").toUpperCase(), filter));
  const counts = Object.fromEntries(["TERPENUHI", "GAP", "EXPIRING", "SUPERSEDED", "REVIEW"].map((status) => [status, findings.filter((item) => String(item.status || "REVIEW").toUpperCase() === status).length]));
  const summary = review.executive_summary || {};
  const status = review.verdict || "—";
  const badgeClass = status === "NO-GO" ? "is-no-go" : status === "BELUM CUKUP BUKTI" ? "is-review" : status === "TIDAK ADA SYARAT TERBACA" ? "is-muted" : "is-go";
  const filters = [["ALL", "Semua", findings.length], ["TERPENUHI", "Terpenuhi", counts.TERPENUHI], ["GAP", "Kesenjangan", counts.GAP], ["NEEDS_REVIEW", "Perlu tindakan", counts.GAP + counts.EXPIRING + counts.REVIEW], ["SUPERSEDED", "Diubah adendum", counts.SUPERSEDED]]
    .map(([value, label, count]) => `<button class="review-filter ${filter === value ? "is-active" : ""}" data-action="review-filter" data-filter="${value}">${label}<span>${number(count)}</span></button>`).join("");
  const tab = state.reviewTab || "matrix";
  const tabs = `<div class="review-tabs" role="tablist" aria-label="Bagian pemeriksaan">
    ${[["matrix", "Temuan dan bukti"], ["proof", "Jejak audit: AI → Python → keputusan"], ["insights", "Ekstraksi AI dan adendum"]].map(([key, label]) => `<button class="review-tab ${tab === key ? "is-active" : ""}" role="tab" aria-selected="${tab === key}" data-action="review-tab" data-tab="${key}">${label}</button>`).join("")}
  </div>`;
  let body;
  if (tab === "insights") body = `<div class="insights-grid">${renderContextual(review.isCustom ? review.contextual_extraction : null)}${renderAdendum(review)}</div>`;
  else if (tab === "proof") body = renderProof(state, review);
  else body = `
    <div class="review-matrix-card"><div class="matrix-heading"><div><p class="eyebrow">MATRIKS PERSYARATAN</p><h3>Persyaratan dan bukti</h3><p>Klik baris untuk melihat kutipan verbatim, rujukan kandidat, hitungan Python, dan mencatat keputusan reviewer.</p></div><div class="matrix-filters" role="group" aria-label="Filter status">${filters}</div></div><div class="review-table-wrap"><table class="review-table"><thead><tr><th>ID / KATEGORI</th><th>KETENTUAN</th><th>STATUS</th><th>BUKTI PENYEDIA</th></tr></thead><tbody>${visible.length ? visible.map((row) => renderFinding(row, state, review, role)).join("") : `<tr><td colspan="4" class="review-empty">${review.isCustom ? "Tidak ada temuan pada filter ini." : "Jalankan evaluasi untuk melihat hasil pemeriksaan."}</td></tr>`}</tbody></table></div><div class="review-table-footer"><span>${number(visible.length)} dari ${number(findings.length)} temuan</span><span>${number(counts.GAP)} kesenjangan · ${number(counts.REVIEW + counts.EXPIRING)} perlu bukti</span></div></div>
    ${renderPenalty(review.isCustom ? review.penalty_simulation : null)}`;
  const hasSource = Boolean(review.has_source_text || review.source_text);
  const risk = review.risk || {};
  const riskMeta = RISK_META[review.risk_level] || RISK_META.NOT_ASSESSABLE;
  const roleCopy = role === "pokja"
    ? { eyebrow: "COMMAND CENTER POKJA · HASIL EVALUASI", title: "Evaluasi kepatuhan & integritas", text: "Periksa kesenjangan, catat keputusan reviewer, lalu terbitkan draf Berita Acara, surat klarifikasi, dan BoQ Excel." }
    : { eyebrow: "TENDER PROTECTION SUITE · HASIL PEMERIKSAAN", title: "Jebakan dokumen & dasar sanggahan", text: "Lengkapi berkas Anda sendiri, lalu susun sanggahan hanya untuk kesenjangan pada dokumen tender dengan kutipan persis." };

  return `<section class="review-workspace" id="risk-review" aria-label="Pemeriksaan persyaratan dan bukti">
    <div class="review-heading">
      <div>
        <p class="eyebrow">${roleCopy.eyebrow}</p>
        <h2>${roleCopy.title}</h2>
        <p>${roleCopy.text}</p>
      </div>
      <div class="review-heading-actions">
        ${review.isCustom ? '<button class="button button-quiet" data-action="add-more-docs">+ Tambah dokumen & jalankan ulang</button>' : ""}
      </div>
    </div>
    <div class="risk-hero ${riskMeta.css}">
      <div class="risk-hero-main">
        <div class="risk-hero-top"><p class="eyebrow">TINGKAT RISIKO ${review.reviewed_by_human ? "· SETELAH REVIEW MANUSIA" : "· HASIL ATURAN DETERMINISTIK"}</p>${engineModeBadge(review.engine_mode)}</div>
        <div class="risk-hero-title">${riskBadge(review.risk_level, { large: true })}<strong class="eligibility-badge ${badgeClass}">${escapeHtml(status)}</strong></div>
        <h3>${escapeHtml(review.package_name)}</h3>
        <p class="risk-rationale">${escapeHtml(risk.rationale || riskMeta.hint)}</p>
        <p class="risk-rule">Aturan ${escapeHtml(risk.rule_applied || "—")} dari tabel keputusan · <button type="button" class="link-button" data-action="review-tab" data-tab="proof">lihat jejak audit</button>${review.reviewed_by_human ? ` · verdict sistem semula: <b>${escapeHtml(review.system_verdict)}</b>` : ""}</p>
        <p class="review-summary-copy">${escapeHtml(review.summary)}</p>
        ${review.coverage?.checks_total ? `<p class="risk-coverage ${review.coverage.low_coverage ? "is-low" : ""}" title="${escapeHtml(review.coverage.note || "")}">Cakupan: ${number(review.coverage.checks_recognized)} dari ${number(review.coverage.checks_total)} pemeriksaan menemukan klausul relevan, dari ${number(review.coverage.requirement_sentences)} kalimat dokumen.</p>` : ""}
      </div>
      <div class="review-kpis">
        <div><span>Kesenjangan</span><strong>${number(counts.GAP)}</strong></div>
        <div><span>Perlu bukti</span><strong>${number(counts.REVIEW + counts.EXPIRING)}</strong></div>
        <div><span>Terpenuhi</span><strong>${number(counts.TERPENUHI)}</strong></div>
        <div><span>Selisih skenario denda</span><strong>${summary.potential_financial_exposure_idr ? rupiah(summary.potential_financial_exposure_idr) : "—"}</strong></div>
      </div>
    </div>
    <div class="role-action-bar" aria-label="Tindak lanjut">${roleActions(review, role, hasSource)}</div>
    ${renderEconomics(state, review)}
    ${tabs}<div class="review-tab-panel">${body}</div>
    <p class="review-caveat">Tingkat risiko adalah hasil tabel keputusan atas teks yang diberikan. Sistem tidak memverifikasi data ke instansi pemerintah, tidak menetapkan kepatuhan, dan tidak memberi nasihat hukum; setiap draf wajib ditinjau manusia.</p></section>`;
}

export { escapeHtml };
