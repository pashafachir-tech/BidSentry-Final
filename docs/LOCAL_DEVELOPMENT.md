# Local development

## Start the application

Use Python 3.11 or newer. There is no npm or frontend build step.

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt        # core app
.venv\Scripts\pip install -r requirements-dev.txt    # optional: tests, lint, job engine, extra providers
Copy-Item .env.example .env
.venv\Scripts\python server.py
```

| Requirements file | Contents |
|---|---|
| `requirements.txt` | Everything the web app needs, including IBM watsonx.ai |
| `requirements-jobs.txt` | Optional async job engine (ARQ, Redis, SQLAlchemy); enable with `BIDSENTRY_JOB_ENGINE=redis` |
| `requirements-dev.txt` | Jobs extras, Gemini/OpenAI providers, pytest, ruff |

## Docker

```bash
docker build -t bidsentry .
docker run -p 8000:8000 -v bidsentry-data:/app/var -e BIDSENTRY_ACCESS_TOKEN=<random> -e BIDSENTRY_POKJA_PIN=<pin> -e BIDSENTRY_VENDOR_PIN=<pin> -e BIDSENTRY_SESSION_SECRET=<random> bidsentry
```

The container listens on `0.0.0.0`, so the server requires `BIDSENTRY_ACCESS_TOKEN` and role PINs; it refuses to start without the token. The audit log and session secret are kept in the `/app/var` volume.

Open `http://127.0.0.1:8000`. The application binds to loopback by default. Set `HOST=0.0.0.0` only when another machine or a container must reach it. `python verify_system.py` checks the API and reports optional integration modes.

## Environment settings

| Setting | Default | Purpose |
|---|---|---|
| `HOST` | `127.0.0.1` | Bind address |
| `PORT` | `8000` | Local HTTP port; `BRIDGE_PORT` remains a fallback alias |
| `MAX_REQUEST_BYTES` | `12582912` | Maximum accepted JSON request body |
| `AUDIT_LOG_PATH` | `audit_log.jsonl` | Append-only local metadata log; relative paths resolve from the repo root |
| `BIDSENTRY_POKJA_PIN` / `BIDSENTRY_VENDOR_PIN` | empty | Role PINs; required on non-loopback hosts. Five wrong PINs lock that client out of the role for 5 minutes |
| `BIDSENTRY_SESSION_SECRET` | generated | HMAC key for the role session cookie |
| `BIDSENTRY_JOB_ENGINE` | empty | `redis` mounts the optional async job API (`requirements-jobs.txt`) |
| `LANGFLOW_ENABLED` | `false` | Enables the optional Langflow advisory adapter |
| `LANGFLOW_URL` | `http://localhost:7860` | Langflow base URL; `LANGFLOW_HOST` remains a fallback alias |
| `LANGFLOW_FLOW_ID` | empty | Flow identifier used at `/api/v1/run/{flow_id}` |
| `LANGFLOW_API_KEY` | empty | Optional key for the configured Langflow server |
| `LANGFLOW_TIMEOUT_SECONDS` | `30` | Langflow request timeout |
| `COMPOSIO_API_KEY` | empty | Enables live Composio actions; otherwise actions are simulated |
| `COMPOSIO_BASE_URL` | Composio execute endpoint | Connector base URL |
| `COMPOSIO_ENTITY_ID` | `default` | Composio entity identifier |
| `COMPOSIO_TIMEOUT_SECONDS` | `30` | Per-action connector timeout |

`LANGFLOW_ENABLED=true` and a flow ID are required before Langflow is considered configured. In addition, the reviewer must explicitly opt in for each audit. The external advisory is supplementary and does not alter the deterministic local score. The flow should accept a chat input string and return readable text. No flow export is included in this repository. HTTP is accepted only for loopback services and Docker's `host.docker.internal` bridge; remote Langflow and Composio endpoints must use HTTPS so API keys are not sent in cleartext.

The same optional settings can be edited from **Koneksi** in the app. The editor writes `.env` atomically and applies new values without restarting. It never returns saved API keys; a blank key field preserves the existing value, and an explicit clear checkbox removes it. The write endpoint accepts loopback requests only and checks browser origin when present. `.env` is plaintext on the local machine and is ignored by Git; keep it private. A remote deployment should use a secrets manager rather than this local editor.

`GET /api/settings/integrations` returns only non-secret values and booleans indicating whether keys are present. `PUT /api/settings/integrations` saves the settings shown in the UI. Both routes are loopback-only. Langflow and Composio timeouts are bounded to 1–120 seconds. The Composio execute URL must include `{action}`.

## Audit request

`POST /api/audit` accepts:

```json
{
  "package_name": "Paket contoh",
  "dok_pemilihan": "Teks RKS/KAK dan klausul kontrak",
  "adendum": "Teks adendum (opsional)",
  "pustaka": "Teks bukti/kredensial (opsional)",
  "allow_external_processing": false
}
```

At least one document field is required. `nama_paket`, `document_text`, `addendum_text`, and `credentials_text` are accepted aliases for earlier clients. Strings are bounded and the complete request is limited by `MAX_REQUEST_BYTES`.

The local rules engine returns `risk_score` from 0 to 100, `risk_level`, `summary`, `findings`, a `verdict`, and an engine descriptor. Every custom audit returns `REVIEW_REQUIRED`, including when no keyword signal is found. For custom audits, keyword detection is only a signal: a matched phrase is not proof that a document is valid, and a missing phrase is not proof of a GAP. These findings use `REVIEW`; a same-line expiry phrase may be marked `EXPIRING`. Detected contract signals also require review. The score does not replace that review step. The scoring bands remain an uncalibrated prioritization heuristic, not a fraud probability or a pass/fail procurement decision.

Audit logs record IDs, risk summaries, and integration status only; submitted document text and evidence snippets are not written to the log. A response may contain masked evidence snippets for the active browser session. Reviewers remain responsible for checking the original source and its current version.

## Document uploads

The audit form can extract `.txt`, `.md`, `.csv`, `.json`, `.docx`, and text-based `.pdf` files. Each file is limited to 8 MB, each DOCX/PDF expanded stream to 8 MB, each PDF to 500 pages, and each document field to 1,000,000 extracted characters. Extraction happens in memory on the local server; source files are not written to disk. DOCX XML with custom DTD/entity declarations is rejected. When the form has filename markers, custom findings include the filename and extracted-text line used for matching. These line references are not original PDF page references. Scanned/image-only PDFs require OCR before upload. PDF text extraction uses `pypdf` when available and a best-effort built-in fallback otherwise. In a multi-file upload, successful files are retained even if another file fails, and failed files are listed for the reviewer.

Live workspace follow-up is a separate, explicit reviewer action. Before sending data through Composio, the app requires consent and shows the package, score, signals, and optional email address that will be shared. It creates a review summary and a provisional internal H+7 reminder; the reminder is not an official procurement deadline. If a recipient address is entered, it also creates a Gmail draft addressed to that person; the app never sends the email. Inspect and correct all outputs in the destination workspace.

## Run checks

```powershell
python -m unittest discover -s tests -v
python -m compileall -q bidsentry server.py verify_system.py
node --input-type=module --check < web/api.js
node --input-type=module --check < web/state.js
node --input-type=module --check < web/render.js
node --input-type=module --check < web/app.js
```

The tests use temporary audit logs and do not call Langflow, Composio, IBM Bob, or other external services.
