"""PDF metadata extraction and cross-vendor metadata comparison.

Metadata matches are investigative signals only. They do not establish common
control, collusion, or document authorship by themselves.
"""

from __future__ import annotations

import hashlib
import io
import math
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

try:
    import pymupdf as fitz
except ImportError:  # The API can still handle text-only evidence when fitz is absent.
    try:
        import fitz
    except ImportError:
        fitz = None

try:
    import pdfplumber
except ImportError:
    pdfplumber = None


MAX_PDF_BYTES = 8 * 1024 * 1024
MAX_PDF_PAGES = 500
_PDF_DATE = re.compile(r"^D:(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?([Zz]|[+-]\d{2}'?\d{2}'?)?")
_ARTIFACT_ANCHORS: dict[str, tuple[str, ...]] = {
    "SIGNATURE": ("tanda tangan", "signature", "signatory", "signed by"),
    "STAMP": ("cap perusahaan", "stempel"),
    "E_METERAI": ("e-meterai", "meterai elektronik", "meterai", "materai"),
}


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().strip("\x00")
    return text or None


def _pdf_datetime(value: Any) -> str | None:
    text = _clean(value)
    if not text:
        return None
    match = _PDF_DATE.match(text)
    if not match:
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).isoformat()
        except ValueError:
            return None
    parts = [int(part or default) for part, default in zip(match.groups()[:6], ("1", "1", "1", "0", "0", "0"))]
    try:
        parsed = datetime(*parts, tzinfo=timezone.utc)
        offset = match.group(7)
        if offset and offset.upper() != "Z":
            sign = 1 if offset[0] == "+" else -1
            digits = re.sub(r"\D", "", offset[1:])
            hours = int(digits[:2])
            minutes = int(digits[2:4] or "0")
            parsed -= timedelta(minutes=sign * (hours * 60 + minutes))
        return parsed.isoformat()
    except ValueError:
        return None


def extract_pdf_metadata(pdf_bytes: bytes) -> dict[str, Any]:
    """Extract non-content PDF metadata and per-document font fingerprints."""
    if not isinstance(pdf_bytes, bytes) or not pdf_bytes:
        return {"status": "invalid_input", "error": "empty_pdf"}
    if len(pdf_bytes) > MAX_PDF_BYTES:
        return {"status": "rejected", "error": "pdf_exceeds_8_mib_limit"}
    if fitz is None:
        return {"status": "unavailable", "error": "pymupdf_not_installed"}

    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
            if len(document) > MAX_PDF_PAGES:
                return {"status": "rejected", "error": "pdf_exceeds_500_page_limit", "page_count": len(document)}
            metadata = document.metadata or {}
            page_fonts: Counter[str] = Counter()
            visual_inventory: list[dict[str, Any]] = []
            page_text: list[dict[str, str]] = []
            for index, page in enumerate(document):
                for font in page.get_fonts(full=True):
                    # Base font, type and encoding are stable enough for comparison,
                    # while resource xrefs are file-specific and intentionally omitted.
                    fingerprint_source = "|".join(str(value or "").strip() for value in (font[3], font[2], font[5]))
                    if fingerprint_source.strip("|"):
                        fingerprint = hashlib.sha256(fingerprint_source.casefold().encode("utf-8")).hexdigest()
                        page_fonts[fingerprint] += 1
                images = page.get_images(full=True)
                image_info = page.get_image_info(xrefs=True)
                drawings = page.get_drawings()
                annotations = page.annots()
                page_ref = f"Page {index + 1}"
                anchor_regions = _artifact_anchor_regions(page)
                soft_mask_xrefs = {int(image[0]) for image in images if len(image) > 1 and image[1]}
                image_regions: list[dict[str, Any]] = []
                page_rect = page.rect
                for info in image_info[:100]:
                    raw_bbox = info.get("bbox")
                    if not isinstance(raw_bbox, (tuple, list)) or len(raw_bbox) != 4:
                        continue
                    bbox = tuple(float(value) for value in raw_bbox)
                    width_pt = max(0.0, bbox[2] - bbox[0])
                    height_pt = max(0.0, bbox[3] - bbox[1])
                    pixel_width = int(info.get("width") or 0)
                    pixel_height = int(info.get("height") or 0)
                    dpi_x = round(pixel_width * 72 / width_pt, 1) if width_pt > 0 and pixel_width else None
                    dpi_y = round(pixel_height * 72 / height_pt, 1) if height_pt > 0 and pixel_height else None
                    xref = int(info.get("xref") or 0)
                    nearby_anchors = [
                        {"artifact_type": anchor["artifact_type"], "label": anchor["label"], "distance_points": round(distance, 1)}
                        for anchor in anchor_regions
                        if (distance := _bbox_distance(bbox, anchor["bbox"])) <= 180
                    ]
                    in_lower_zone = bbox[1] >= page_rect.height * 0.55
                    image_regions.append({
                        "bbox": [round(value, 1) for value in bbox],
                        "pixel_width": pixel_width,
                        "pixel_height": pixel_height,
                        "dpi_x": dpi_x,
                        "dpi_y": dpi_y,
                        "has_soft_mask": xref in soft_mask_xrefs,
                        "in_lower_page_zone": in_lower_zone,
                        "nearby_artifact_anchors": nearby_anchors,
                    })
                artifact_regions: list[dict[str, Any]] = []
                for anchor in anchor_regions[:100]:
                    matching_images = [
                        image for image in image_regions
                        if _bbox_distance(image["bbox"], anchor["bbox"]) <= 180
                    ]
                    artifact_regions.append({
                        "artifact_type": anchor["artifact_type"],
                        "anchor_label": anchor["label"],
                        "nearby_image_count": len(matching_images),
                        "nearby_images": matching_images[:10],
                        "nearby_vector_drawing_count": sum(
                            1 for drawing in drawings
                            if _bbox_distance(tuple(drawing["rect"]), anchor["bbox"]) <= 60
                        ),
                        "bbox": [round(value, 1) for value in anchor["bbox"]],
                    })
                visual_inventory.append({
                    "page_ref": page_ref,
                    "raster_image_count": len(images),
                    "image_inventory_truncated": len(image_info) > 100,
                    "soft_mask_image_count": sum(1 for image in images if len(image) > 1 and image[1]),
                    "vector_drawing_count": len(drawings),
                    "annotation_count": sum(1 for _ in annotations) if annotations else 0,
                    "artifact_anchor_count": len(anchor_regions),
                    "artifact_candidate_regions": artifact_regions,
                })
                page_text.append({"page_ref": page_ref, "text": page.get_text("text")})

            trailer_id = None
            try:
                key_type, key_value = document.xref_get_key(-1, "ID")
                if key_type not in {"null", "none"}:
                    trailer_id = _clean(key_value)
            except (AttributeError, RuntimeError, ValueError):
                trailer_id = None
            document_uuid = hashlib.sha256(trailer_id.encode("utf-8")).hexdigest() if trailer_id else None
            fonts = [{"fingerprint": key, "resource_count": count} for key, count in sorted(page_fonts.items())]
            text_page_count = sum(1 for page in page_text if page["text"].strip())
            page_tables: list[dict[str, Any]] = []
            table_extraction_status = "unavailable" if pdfplumber is None else "completed"
            if pdfplumber is not None:
                try:
                    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf_document:
                        for index, page in enumerate(pdf_document.pages):
                            for rows in page.extract_tables() or []:
                                page_tables.append({"page_ref": f"Page {index + 1}", "rows": rows})
                except Exception:
                    table_extraction_status = "failed"
            return {
                "status": "extracted",
                "page_count": len(document),
                "nonempty_text_page_count": text_page_count,
                "ocr_required_page_count": len(document) - text_page_count,
                "author": _clean(metadata.get("author")),
                "creator": _clean(metadata.get("creator")),
                "producer": _clean(metadata.get("producer")),
                "creation_date": _pdf_datetime(metadata.get("creationDate")),
                "modification_date": _pdf_datetime(metadata.get("modDate")),
                "document_uuid_sha256": document_uuid,
                "font_fingerprints": fonts,
                "font_fingerprint_count": len(fonts),
                "page_text": page_text,
                "page_visual_inventory": visual_inventory,
                "page_tables": page_tables,
                "table_extraction_status": table_extraction_status,
            }
    except Exception as exc:  # MuPDF can raise multiple native and parser exceptions.
        return {"status": "invalid_pdf", "error": type(exc).__name__}


def compare_vendor_metadata(vendors: list[dict[str, Any]], suspicious_minutes: int = 10) -> dict[str, Any]:
    """Find shared metadata profiles, PDF IDs and tightly clustered submissions."""
    alerts: list[dict[str, Any]] = []
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for index, first in enumerate(vendors):
        for second in vendors[index + 1:]:
            if str(first.get("vendor_id", "")) == str(second.get("vendor_id", "")):
                continue
            pairs.append((first, second))

    def metadata_of(vendor: dict[str, Any]) -> dict[str, Any]:
        metadata = vendor.get("document_metadata")
        return metadata if isinstance(metadata, dict) else {}

    for first, second in pairs:
        a, b = metadata_of(first), metadata_of(second)
        names = (first.get("vendor_name", first.get("vendor_id")), second.get("vendor_name", second.get("vendor_id")))
        shared_author = _normalized(a.get("author")) and _normalized(a.get("author")) == _normalized(b.get("author"))
        shared_creator = _normalized(a.get("creator")) and _normalized(a.get("creator")) == _normalized(b.get("creator"))
        shared_producer = _normalized(a.get("producer")) and _normalized(a.get("producer")) == _normalized(b.get("producer"))
        if shared_author or shared_creator:
            alerts.append({
                "signal": "SHARED_AUTHOR_PROFILE",
                "vendors": list(names),
                "severity": "LOW",
                "details": "Profil author/creator PDF identik; dapat berasal dari perangkat lunak, perangkat, atau templat bersama.",
            })
        if shared_producer:
            alerts.append({
                "signal": "SHARED_PDF_PRODUCER",
                "vendors": list(names),
                "severity": "LOW",
                "details": "Perangkat lunak producer PDF sama; kecocokan umum ini tidak membuktikan kendali bersama.",
            })
        uuid_a = a.get("document_uuid_sha256") or a.get("system_uuid_sha256") or _hash_if_present(a.get("document_uuid") or a.get("system_uuid"))
        uuid_b = b.get("document_uuid_sha256") or b.get("system_uuid_sha256") or _hash_if_present(b.get("document_uuid") or b.get("system_uuid"))
        if uuid_a and uuid_a == uuid_b:
            alerts.append({
                "signal": "MATCHING_PDF_DOCUMENT_ID",
                "vendors": list(names),
                "severity": "HIGH",
                "details": "PDF document ID yang sama terdeteksi; verifikasi berkas asli dan riwayat ekspor.",
            })
        for date_field, signal, label in (
            ("creation_date", "MATCHING_PDF_CREATION_TIMESTAMP", "creation"),
            ("modification_date", "MATCHING_PDF_MODIFICATION_TIMESTAMP", "modification"),
        ):
            date_a, date_b = _normalized(a.get(date_field)), _normalized(b.get(date_field))
            if date_a and date_a == date_b:
                alerts.append({
                    "signal": signal,
                    "vendors": list(names),
                    "severity": "LOW",
                    "timestamp": date_a,
                    "details": f"Waktu {label} PDF sama; dapat berasal dari salinan templat atau proses ekspor bersama dan perlu diverifikasi.",
                })
        fonts_a = {item.get("fingerprint") for item in a.get("font_fingerprints", []) if isinstance(item, dict)}
        fonts_b = {item.get("fingerprint") for item in b.get("font_fingerprints", []) if isinstance(item, dict)}
        if fonts_a and fonts_b and fonts_a == fonts_b:
            alerts.append({
                "signal": "IDENTICAL_FONT_FINGERPRINTS",
                "vendors": list(names),
                "severity": "LOW",
                "details": "Himpunan fingerprint font identik; sinyal lemah yang umum pada dokumen bertemplat sama.",
            })
        delta = _submission_delta(first.get("submission_timestamp"), second.get("submission_timestamp"))
        if delta is not None and delta < timedelta(minutes=suspicious_minutes):
            alerts.append({
                "signal": "CLOSE_SUBMISSION_TIMESTAMPS",
                "vendors": list(names),
                "severity": "MEDIUM",
                "minutes_apart": round(delta.total_seconds() / 60, 2),
                "details": f"Waktu penyerahan berjarak kurang dari {suspicious_minutes} menit; konfirmasi log portal resmi.",
            })

    return {
        "status": "screened" if len(vendors) > 1 else "insufficient_comparison_data",
        "compared_vendor_count": len(vendors),
        "pair_count": len(pairs),
        "alerts": alerts,
        "interpretation": "Sinyal metadata tidak membuktikan bid-rigging; tinjau sumber dan konteks secara independen.",
    }


def _normalized(value: Any) -> str | None:
    text = _clean(value)
    return " ".join(text.casefold().split()) if text else None


def _artifact_anchor_regions(page: Any) -> list[dict[str, Any]]:
    regions: list[dict[str, Any]] = []
    seen: set[tuple[str, str, tuple[float, ...]]] = set()
    for artifact_type, terms in _ARTIFACT_ANCHORS.items():
        for term in terms:
            try:
                rectangles = page.search_for(term, quads=False)
            except (AttributeError, RuntimeError, ValueError):
                continue
            for rectangle in rectangles:
                bbox = tuple(float(value) for value in rectangle)
                identity = (artifact_type, term, tuple(round(value, 1) for value in bbox))
                if identity in seen:
                    continue
                seen.add(identity)
                regions.append({"artifact_type": artifact_type, "label": term, "bbox": bbox})
    return regions


def _bbox_distance(first: tuple[float, ...], second: tuple[float, ...]) -> float:
    if len(first) != 4 or len(second) != 4:
        return math.inf
    dx = max(first[0] - second[2], second[0] - first[2], 0.0)
    dy = max(first[1] - second[3], second[1] - first[3], 0.0)
    return math.hypot(dx, dy)


def _hash_if_present(value: Any) -> str | None:
    text = _clean(value)
    return hashlib.sha256(text.encode("utf-8")).hexdigest() if text else None


def _submission_delta(first: Any, second: Any) -> timedelta | None:
    try:
        a = first if isinstance(first, datetime) else datetime.fromisoformat(str(first).replace("Z", "+00:00"))
        b = second if isinstance(second, datetime) else datetime.fromisoformat(str(second).replace("Z", "+00:00"))
        if a.tzinfo is None:
            a = a.replace(tzinfo=timezone.utc)
        if b.tzinfo is None:
            b = b.replace(tzinfo=timezone.utc)
        return abs(a.astimezone(timezone.utc) - b.astimezone(timezone.utc))
    except (TypeError, ValueError, OverflowError):
        return None
