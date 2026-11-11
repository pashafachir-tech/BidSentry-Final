# Status Integrasi Teknologi IBM & Layanan Eksternal

> **Dokumen Transparansi Teknis**: Dihasilkan oleh `scripts/verify_watsonx.py`.
> Terakhir diperbarui: 2026-11-09 11:01:56 UTC

Dokumen ini mendokumentasikan status sebenarnya tanpa klaim palsu (No Fabricated Data). Evaluator dan juri dapat memverifikasi status secara mandiri.

---

## 1. IBM watsonx.ai

| Komponen | Status Saat Ini | Keterangan |
| :--- | :--- | :--- |
| **Kredensial** | `VERIFIED_ONLINE` | `Terautentikasi ke IBM watsonx; spesifikasi model mistralai/mistral-small-3-1-24b-instruct-2503 berhasil diambil.` |
| **Model ID** | `mistralai/mistral-small-3-1-24b-instruct-2503` | Model chat yang dipanggil lewat watsonx Chat API (dapat diganti via `WATSONX_MODEL_ID`) |
| **Latensi Uji** | `6254.66 ms` | Nilai aktual saat probe dijalankan |
| **Uji Generasi** | — | success pada 2026-11-09 11:01 UTC: 600 token masuk, 157 token keluar, 4521.2 ms, 2 kutipan terverifikasi, 0 ditolak (dokumen sintetis). |
| **Panduan Aktivasi** | — | Setel WATSONX_API_KEY dan WATSONX_PROJECT_ID pada environment atau file .env lokal untuk mengaktifkan ekstraksi semantik via IBM watsonx.ai. |

### Peran IBM watsonx dalam Arsitektur BidSentry:
- **Tingkat 1 (Local Engine)**: Menjalankan aturan deterministik di server BidSentry tanpa LLM dan tanpa koneksi keluar.
- **Tingkat 2 (watsonx.ai)**: Bila disetujui pengguna per audit, model di IBM watsonx.ai mengekstrak kutipan (merek, jadwal, adendum, personel, SLA) dari cuplikan maksimal 48.000 karakter yang sudah disensor. Kutipan dicocokkan persis dengan dokumen. Kandidat yang lolos aturan Python menjadi temuan; kandidat merek di luar pola aturan ditampilkan untuk dicek manusia dan tidak memengaruhi verdict.

---

## 2. IBM Bob / Langflow MCP (Model Context Protocol)

| Komponen | Status Saat Ini | Keterangan |
| :--- | :--- | :--- |
| **Konfigurasi MCP** | `CONFIG_PRESENT` | `Konfigurasi Bob MCP server terverifikasi di bob/mcp.json (transport stdio, target: Langflow port 7860).` Hanya berkas konfigurasi; koneksi end-to-end belum diuji. |
| **Transport** | `stdio` | Standar MCP specification |
| **Target Eksekusi** | `langflow run --mcp-server` | Port 7860 |
| **Panduan Aktivasi** | — | Jalankan Langflow lokal di port 7860 untuk menghubungkan agentic MCP server. |

### Peran MCP dalam Arsitektur:
- Menjembatani agent LLM dengan tool pengadaan lokal BidSentry melalui protokol standar MCP.
- Memungkinkan IDE agentic (seperti IBM Bob / Claude Desktop) memanggil fungsi audit pengadaan secara terstruktur.

---

## 3. Komponen Pendukung Lainnya

- **Mesin Aturan Lokal**: `READY` (31 aturan deklaratif aktif secara deterministik dan offline).
- **Langflow Advisory**: Terintegrasi via HTTP REST client (`bidsentry/services/langflow_service.py`), mode opt-in dengan konfirmasi manual pengguna.
- **Composio Automation**: Integrasi kalender dan dokumen tender, mode human-in-the-loop (memerlukan persetujuan eksplisit sebelum menyiapkan aksi).
