#!/usr/bin/env python3
"""
BidSentry — Composio Dispatcher
=================================
Prepares 3 workspace follow-up artifacts through the Composio REST API:

  1. GOOGLEDOCS_CREATE_DOCUMENT_MARKDOWN  — Review summary for human verification
  2. GOOGLECALENDAR_CREATE_EVENT — Provisional internal reminder (H+7)
  3. GMAIL_CREATE_EMAIL_DRAFT    — Unaddressed internal review draft

All I/O uses Python stdlib only (urllib.request, json, os, datetime).
No third-party pip dependencies are required.

Environment:
    COMPOSIO_API_KEY  — Composio API key (required for live mode)
                        Falls back to reading .env file if not set in env.

"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any
from bidsentry.config import Settings, load_env_file


# ─── Configuration ────────────────────────────────────────────────────────────

load_env_file()


def _get_api_key() -> str | None:
    """Return the Composio API key from the centralized environment config."""
    return os.environ.get("COMPOSIO_API_KEY", "").strip() or None


# ─── Low-level HTTP helper ────────────────────────────────────────────────────

def _post_composio(action: str, api_key: str, params: dict, settings: Any = None) -> dict:
    """
    POST to the Composio execute endpoint for *action*.
    Returns the parsed JSON response dict.
    Raises urllib.error.URLError / urllib.error.HTTPError on network failure.
    """
    cfg = settings or Settings.from_environment()
    url     = cfg.composio_base_url.format(action=urllib.parse.quote(action, safe=""))
    payload = json.dumps({
        "user_id": cfg.composio_entity_id,
        "version": "latest",
        "arguments": params,
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data    = payload,
        method  = "POST",
        headers = {
            "Content-Type":  "application/json",
            "Accept":        "application/json",
            "x-api-key":     api_key,
        },
    )
    with urllib.request.urlopen(req, timeout=cfg.composio_timeout_seconds) as resp:
        response_body = resp.read(2 * 1024 * 1024 + 1)
    if len(response_body) > 2 * 1024 * 1024:
        raise ValueError("Composio response exceeds the 2 MB limit.")
    response_data = json.loads(response_body.decode("utf-8"))
    if not isinstance(response_data, dict):
        raise ValueError("Composio returned an invalid response object.")
    return response_data


def test_composio_connection(settings: Settings | None = None) -> dict:
    """Read connected-account metadata only; this never creates external artifacts."""
    config = settings or Settings.from_environment()
    if not config.composio_api_key:
        return {"status": "not_configured", "message": "COMPOSIO_API_KEY belum diatur."}

    marker = "/tools/execute/"
    base = config.composio_base_url
    if marker not in base:
        return {"status": "invalid_configuration", "message": "URL Composio harus memakai endpoint tools/execute v3.1."}
    api_root = base.split(marker, 1)[0]
    query = urllib.parse.urlencode({"user_ids": config.composio_entity_id, "limit": "50"})
    request = urllib.request.Request(
        f"{api_root}/connected_accounts?{query}",
        headers={"Accept": "application/json", "x-api-key": config.composio_api_key},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=config.composio_timeout_seconds) as response:
            body = response.read(256 * 1024 + 1)
        if len(body) > 256 * 1024:
            return {"status": "invalid_response", "message": "Daftar akun Composio melebihi batas 256 KB."}
        data = json.loads(body.decode("utf-8")) if body else {}
        if not isinstance(data, dict):
            return {"status": "invalid_response", "message": "Daftar akun Composio tidak memiliki format yang dikenal."}
        accounts = data.get("items")
        if not isinstance(accounts, list):
            nested = data.get("data")
            accounts = nested.get("items") if isinstance(nested, dict) else nested if isinstance(nested, list) else None
        if not isinstance(accounts, list):
            return {"status": "invalid_response", "message": "Daftar akun Composio tidak memiliki format yang dikenal."}
        toolkits: set[str] = set()
        active_accounts = 0
        for account in accounts:
            if not isinstance(account, dict):
                continue
            status = str(account.get("status", "")).upper()
            if status == "ACTIVE":
                active_accounts += 1
                toolkit = account.get("toolkit")
                slug = toolkit.get("slug") if isinstance(toolkit, dict) else account.get("toolkit_slug")
                if isinstance(slug, str) and slug.strip():
                    toolkits.add(slug.strip().upper())
        connection_status = "connected" if active_accounts else "authenticated_no_active_accounts" if accounts else "authenticated_no_accounts"
        return {
            "status": connection_status,
            "api_key_valid": True,
            "active_account_count": active_accounts,
            "linked_toolkits": sorted(toolkits),
            "message": "API Composio terhubung; metadata akun dibaca tanpa menjalankan aksi." if active_accounts else "API key valid, tetapi belum ada connected account aktif untuk User ID ini.",
        }
    except urllib.error.HTTPError as exc:
        status = "auth_failed" if exc.code in {401, 403} else "provider_error"
        message = "API key Composio ditolak." if status == "auth_failed" else f"Composio merespons HTTP {exc.code}."
        return {"status": status, "message": message}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"status": "unreachable", "error_type": type(exc).__name__, "message": "Composio tidak dapat dijangkau."}
    except (ValueError, json.JSONDecodeError):
        return {"status": "invalid_response", "message": "Respons Composio bukan JSON yang valid."}


# ─── Action builders ──────────────────────────────────────────────────────────

def _build_docs_params(audit_data: dict) -> dict:
    """Build the input dict for GOOGLEDOCS_CREATE_DOCUMENT_MARKDOWN."""
    package_name   = audit_data.get("nama_paket", "Audit pengadaan")
    verdict        = audit_data.get("verdict", "GO-WITH-CAUTION")
    risk_label     = {"NOT_ASSESSABLE": "Tidak Dapat Dinilai", "LOW": "Rendah", "MEDIUM": "Sedang", "HIGH": "Tinggi", "CRITICAL": "Kritis"}.get(str(audit_data.get("risk_level", "")), "—")
    alasan         = audit_data.get("alasan_utama", [])
    now_str        = datetime.now(tz=timezone(timedelta(hours=7))).strftime("%d %B %Y %H:%M WIB")

    body = "\n\n".join([
        "BIDSENTRY AUDIT DOSSIER",
        f"Paket   : {package_name}",
        f"ID      : {audit_data.get('tender_id') or '—'}",
        f"Dibuat  : {now_str}",
        f"Status review : {verdict}",
        f"Tingkat risiko: {risk_label}",
        "",
        "═══ SINYAL UNTUK VERIFIKASI MANUAL ═══",
        "\n".join(f"• {a}" for a in alasan),
        "",
        "Ketiadaan sinyal bukan bukti kepatuhan; periksa dokumen dan bukti sumber.",
        "",
        "─────────────────────────────────────────────────────────",
        "Dibuat sebagai ringkasan review. Indeks triase bukan verdict hukum, kepatuhan, atau fraud.",
        "Reviewer wajib memeriksa dokumen asli sebelum tindak lanjut atau keputusan.",
    ])

    return {
        "title": f"BidSentry Audit Dossier - {package_name}",
        "markdown_text": body,
    }


def _build_calendar_params(audit_data: dict) -> dict:
    """Build a provisional internal reminder (H+7, 09:00–09:30 WIB)."""
    package_name = audit_data.get("nama_paket", "Audit pengadaan")
    wib = timezone(timedelta(hours=7))
    now = datetime.now(tz=wib)
    event_date = now + timedelta(days=7)
    start = event_date.replace(hour=9, minute=0, second=0, microsecond=0)
    reasons = audit_data.get("alasan_utama", [])
    reason_summary = "; ".join(reasons[:2]) if reasons else "Belum ada ringkasan sinyal; periksa review di BidSentry."

    description = (
        f"Pengingat internal untuk meninjau paket: {package_name}.\n"
        f"Sinyal untuk diverifikasi: {reason_summary}\n\n"
        "Waktu H+7 ini adalah pengingat default, bukan tenggat resmi tender. "
        "Periksa dan ubah tanggal berdasarkan jadwal resmi sebelum mengandalkannya."
    )
    start_utc = start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "summary": f"[BidSentry] Pengingat review internal — {package_name}",
        "description": description,
        "start_datetime": start_utc,
        "event_duration_minutes": 30,
        "timezone": "Asia/Jakarta",
    }

def _build_gmail_params(audit_data: dict) -> dict:
    """Build an internal review draft; it never sends an email."""
    package_name = audit_data.get("nama_paket", "Audit pengadaan")
    now_str = datetime.now(tz=timezone(timedelta(hours=7))).strftime("%d %B %Y")
    reasons = audit_data.get("alasan_utama", [])
    reason_lines = "\n".join(f"{i}. {reason}" for i, reason in enumerate(reasons, 1))
    body = (
        "Dengan hormat,\n\n"
        f"Mohon dilakukan peninjauan internal atas paket: {package_name}.\n"
        f"Ringkasan sinyal BidSentry ({now_str}) untuk diverifikasi terhadap dokumen sumber:\n\n"
        + (reason_lines or "Belum ada sinyal yang ditampilkan. Periksa dokumen sumber secara menyeluruh.")
        + "\n\nCatatan: indeks triase dan sinyal aturan bukan kesimpulan hukum, kepatuhan, atau fraud. "
        "Cocokkan setiap poin dengan dokumen dan versi yang berlaku sebelum mengambil tindakan.\n\n"
        "Hormat kami,\n[Nama dan jabatan]"
    )
    return {
        "recipient_email": audit_data.get("email_penerima", ""),
        "subject": f"[Draf BidSentry] Review internal — {package_name}",
        "body": body,
    }


# ─── Main dispatcher ──────────────────────────────────────────────────────────

def dispatch_tender_workspace(audit_data: dict, settings: Any = None) -> dict:
    """
    Execute 3 Composio actions for the given audit data.

    Returns a structured JSON-serialisable dict with actual connector status.

    This function never raises — all exceptions are caught and returned
    as structured error payloads so the calling server stays alive.
    """
    if settings is not None:
        api_key = (getattr(settings, "composio_api_key", "") or "").strip() or None
    else:
        api_key = _get_api_key()
    action_plan = [
        ("GOOGLEDOCS_CREATE_DOCUMENT_MARKDOWN", _build_docs_params(audit_data)),
        ("GOOGLECALENDAR_CREATE_EVENT", _build_calendar_params(audit_data)),
    ]
    if audit_data.get("email_penerima"):
        action_plan.append(("GMAIL_CREATE_EMAIL_DRAFT", _build_gmail_params(audit_data)))

    results: dict = {
        "status":    "unknown",
        "actions":   {},
        "errors":    [],
    }

    # ── Guard: missing API key ─────────────────────────────────────────────
    if not api_key:
        results["status"] = "unavailable"
        results["message"] = "COMPOSIO_API_KEY belum dikonfigurasi; tidak ada tindakan yang dijalankan."
        return results

    # ── Live: call Composio ────────────────────────────────────────────────
    success_count = 0
    for action_name, params in action_plan:
        try:
            response = _post_composio(action_name, api_key, params, settings=settings)
            succeeded = response.get("successful") is True
            data = response.get("data", response.get("response_data", {}))
            if not isinstance(data, dict):
                data = {"result": data}
            if succeeded:
                results["actions"][action_name] = {"success": True, "data": data}
                success_count += 1
            else:
                error_value = response.get("error")
                error_code = error_value.get("code") or error_value.get("slug") if isinstance(error_value, dict) else None
                suffix = f" (kode {str(error_code)[:80]})" if error_code else ""
                err_msg = f"{action_name}: Composio melaporkan aksi gagal{suffix}."
                results["errors"].append(err_msg)
                results["actions"][action_name] = {"success": False, "error": err_msg, "data": {}}
        except urllib.error.HTTPError as exc:
            err_msg = f"{action_name}: HTTP {exc.code} dari Composio."
            results["errors"].append(err_msg)
            results["actions"][action_name] = {
                "success":   False,
                "error":     err_msg,
                "data":      {},
            }
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            err_msg = f"{action_name}: Connection error — {exc}"
            results["errors"].append(err_msg)
            results["actions"][action_name] = {
                "success":   False,
                "error":     err_msg,
                "data":      {},
            }
        except Exception as exc:  # noqa: BLE001
            err_msg = f"{action_name}: kegagalan tak terduga ({type(exc).__name__})."
            results["errors"].append(err_msg)
            results["actions"][action_name] = {
                "success":   False,
                "error":     err_msg,
                "data":      {},
            }

    # Determine overall status
    if success_count == len(action_plan):
        results["status"] = "success"
    elif success_count > 0:
        results["status"] = "partial"
    else:
        results["status"] = "error"

    # Convenience top-level URLs
    doc_data   = results["actions"].get("GOOGLEDOCS_CREATE_DOCUMENT_MARKDOWN",  {}).get("data", {})
    cal_data   = results["actions"].get("GOOGLECALENDAR_CREATE_EVENT", {}).get("data", {})
    gmail_data = results["actions"].get("GMAIL_CREATE_EMAIL_DRAFT",    {}).get("data", {})

    # Composio may nest under "response_data" or return directly — handle both
    results["doc_url"]   = (
        doc_data.get("documentUrl")
        or doc_data.get("document_url")
        or doc_data.get("url")
        or doc_data.get("response_data", {}).get("documentUrl")
        or (f"https://docs.google.com/document/d/{doc_data.get('documentId') or doc_data.get('document_id')}/edit" if doc_data.get("documentId") or doc_data.get("document_id") else None)
    )
    results["event_url"] = (
        cal_data.get("eventUrl")
        or cal_data.get("htmlLink")
        or cal_data.get("response_data", {}).get("htmlLink")
    )
    results["draft_url"] = (
        gmail_data.get("draftUrl")
        or gmail_data.get("response_data", {}).get("id")
    )

    return results
