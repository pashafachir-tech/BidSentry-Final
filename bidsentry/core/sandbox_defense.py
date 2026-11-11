"""Conservative PDF/text screening for hidden content and prompt injection.

Findings are triage signals. OCR differences and text styling cannot establish
intent, document authenticity, or fraud on their own.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from bisect import bisect_right
from collections import Counter
from collections.abc import Callable
from typing import Any

try:
    import pymupdf as fitz
except ImportError:  # Text-only deployments can still sanitize supplied chunks.
    try:
        import fitz
    except ImportError:
        fitz = None


LOGGER = logging.getLogger("bidsentry.sandbox_defense")
MAX_PDF_BYTES = 8 * 1024 * 1024
MAX_PDF_PAGES = 500
HIDDEN_TEXT_RATIO_THRESHOLD = 0.25
_ZERO_WIDTH = re.compile("[\u200b-\u200f\u202a-\u202e\u2060\ufeff]")
_WORD = re.compile(r"[\wÀ-ÿ]+", re.UNICODE)
_INJECTION_PATTERNS = (
    re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?", re.I),
    re.compile(r"disregard\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?", re.I),
    re.compile(r"mark\s+(?:this|the\s+(?:bid|proposal|document))\s+(?:as\s+)?compliant", re.I),
    re.compile(r"(?:reveal|print|exfiltrate)\s+(?:the\s+)?(?:system\s+)?prompt", re.I),
    re.compile(r"(?:assistant|system)\s*:\s*(?:ignore|override|follow)", re.I),
    re.compile(r"bỏ\s+qua\s+(?:mọi\s+)?(?:chỉ\s+dẫn|instruksi)\s+sebelumnya", re.I),
)


def sanitize_untrusted_text(text: str) -> dict[str, Any]:
    """Remove zero-width controls and instruction-like lines from model input."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    without_controls = _ZERO_WIDTH.sub("", text)
    lines = without_controls.splitlines()
    offsets: list[int] = []
    position = 0
    for line in lines:
        offsets.append(position)
        position += len(line) + 1
    injection_lines: set[int] = set()
    combined = "\n".join(lines)
    for pattern in _INJECTION_PATTERNS:
        for match in pattern.finditer(combined):
            first_line = max(0, bisect_right(offsets, match.start()) - 1)
            last_line = max(first_line, bisect_right(offsets, max(match.end() - 1, match.start())) - 1)
            injection_lines.update(range(first_line, last_line + 1))
    findings: list[dict[str, Any]] = []
    kept_lines: list[str] = []
    for line_index, line in enumerate(lines):
        if line_index in injection_lines:
            line_number = line_index + 1
            findings.append({
                "type": "PROMPT_INJECTION_TEXT",
                "line": line_number,
                "excerpt": line.strip()[:240],
                "action": "line_removed_from_model_input",
            })
            continue
        kept_lines.append(line)
    sanitized = "\n".join(kept_lines)
    if without_controls.endswith(("\n", "\r")) and kept_lines:
        sanitized += "\n"
    return {
        "sanitized_text": sanitized,
        "findings": findings,
        "zero_width_characters_removed": len(_ZERO_WIDTH.findall(text)),
        "removed_line_count": len(findings),
    }


def inspect_text_chunks(pages: list[dict[str, str]]) -> dict[str, Any]:
    """Inspect caller-supplied extracted text when original PDF bytes are absent."""
    page_results: list[dict[str, Any]] = []
    for page in pages:
        page_ref = str(page.get("page_ref") or "")
        raw_text = str(page.get("text") or "")
        cleaned = sanitize_untrusted_text(raw_text)
        findings = [dict(item, page_ref=page_ref) for item in cleaned["findings"]]
        if cleaned["zero_width_characters_removed"]:
            findings.append({
                "type": "ZERO_WIDTH_CONTROL_CHARACTERS",
                "page_ref": page_ref,
                "count": cleaned["zero_width_characters_removed"],
                "action": "characters_removed_from_model_input",
            })
        page_results.append({
            "page_ref": page_ref,
            "sanitized_text": cleaned["sanitized_text"],
            "findings": findings,
            "ocr_comparison_status": "not_available_without_original_pdf",
        })
    all_findings = [finding for page in page_results for finding in page["findings"]]
    return {
        "status": "screened" if pages else "no_text_pages",
        "page_count": len(page_results),
        "findings": all_findings,
        "pages": page_results,
        "interpretation": "Teks pemasukan dihapus dari prompt model; sumber asli dipertahankan untuk pemeriksaan kutipan eksak.",
    }


def inspect_pdf(
    pdf_bytes: bytes,
    *,
    ocr_extractor: Callable[[Any, int], str] | None = None,
    run_native_ocr: bool = True,
) -> dict[str, Any]:
    """Inspect PDF spans and compare digital text with OCR-rendered page text.

    ``ocr_extractor`` receives a PyMuPDF page and its one-based page number.
    Without a callback, PyMuPDF's Tesseract bridge is attempted per page.
    OCR failures are recorded as unavailable and never treated as clean pages.
    """
    if not isinstance(pdf_bytes, bytes) or not pdf_bytes:
        return {"status": "invalid_input", "error": "empty_pdf", "findings": [], "pages": []}
    if len(pdf_bytes) > MAX_PDF_BYTES:
        return {"status": "rejected", "error": "pdf_exceeds_8_mib_limit", "findings": [], "pages": []}
    if fitz is None:
        return {"status": "unavailable", "error": "pymupdf_not_installed", "findings": [], "pages": []}
    try:
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        LOGGER.info("PDF sandbox could not open input", extra={"error_type": type(exc).__name__})
        return {"status": "invalid_pdf", "error": type(exc).__name__, "findings": [], "pages": []}
    with document:
        if len(document) > MAX_PDF_PAGES:
            return {"status": "rejected", "error": "pdf_exceeds_500_page_limit", "page_count": len(document), "findings": [], "pages": []}
        page_results: list[dict[str, Any]] = []
        all_findings: list[dict[str, Any]] = []
        ocr_available_count = 0
        for page_index, page in enumerate(document):
            page_ref = f"Page {page_index + 1}"
            raw_text = page.get_text("text") or ""
            raw_dict = page.get_text("dict")
            try:
                page_pixmap = page.get_pixmap(matrix=fitz.Matrix(0.25, 0.25), colorspace=fitz.csRGB, alpha=False)
            except Exception as exc:
                page_pixmap = None
                LOGGER.debug("PDF page background sampling unavailable", extra={"page": page_index + 1, "error_type": type(exc).__name__})
            findings: list[dict[str, Any]] = []
            hidden_spans: list[str] = []
            for block in raw_dict.get("blocks", []):
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        span_text = str(span.get("text") or "")
                        if not span_text.strip():
                            continue
                        color = span.get("color")
                        size = span.get("size")
                        background_color = _sample_background_color(page_pixmap, page.rect, span.get("bbox"))
                        matching_background = (
                            isinstance(color, int)
                            and background_color is not None
                            and _colors_match(_rgb(color), background_color)
                        )
                        near_white = isinstance(color, int) and color >= 0xF5F5F5
                        white_background_match = near_white and (
                            background_color is None or _colors_match(_rgb(color), background_color)
                        )
                        if matching_background or white_background_match:
                            hidden_spans.append(span_text)
                            findings.append({
                                "type": "WHITE_OR_NEAR_WHITE_TEXT" if white_background_match else "BACKGROUND_MATCHING_TEXT",
                                "excerpt": span_text[:240],
                                "font_size": size,
                                "font_color_rgb": _rgb(color),
                                "background_color_rgb": background_color,
                            })
                        if isinstance(size, (int, float)) and size <= 1.0:
                            hidden_spans.append(span_text)
                            findings.append({"type": "TINY_FONT_TEXT", "excerpt": span_text[:240], "font_size": float(size)})
            try:
                for trace in page.get_texttrace():
                    trace_text = str(trace.get("chars", ""))
                    # PyMuPDF returns character tuples in `chars`; reconstruct their text.
                    if isinstance(trace.get("chars"), (tuple, list)):
                        trace_text = "".join(chr(item[0]) for item in trace["chars"] if isinstance(item, (tuple, list)) and item and isinstance(item[0], int) and 0 <= item[0] <= 0x10FFFF)
                    opacity = trace.get("opacity", 1)
                    rendering_type = trace.get("type")
                    if trace_text.strip() and (rendering_type == 3 or isinstance(opacity, (int, float)) and opacity <= 0.05):
                        hidden_spans.append(trace_text)
                        findings.append({"type": "INVISIBLE_TEXT_RENDER_MODE", "excerpt": trace_text[:240], "rendering_type": rendering_type, "opacity": opacity})
            except (AttributeError, RuntimeError, ValueError, TypeError):
                pass

            cleaned = sanitize_untrusted_text(raw_text)
            findings.extend(dict(item, page_ref=page_ref) for item in cleaned["findings"])
            if cleaned["zero_width_characters_removed"]:
                findings.append({"type": "ZERO_WIDTH_CONTROL_CHARACTERS", "page_ref": page_ref, "count": cleaned["zero_width_characters_removed"], "action": "characters_removed_from_model_input"})
            removed_hidden: set[str] = set()
            for hidden in hidden_spans:
                if not hidden or hidden in removed_hidden:
                    continue
                removed_hidden.add(hidden)
                cleaned["sanitized_text"] = cleaned["sanitized_text"].replace(hidden, "")
                if any(pattern.search(hidden) for pattern in _INJECTION_PATTERNS):
                    findings.append({"type": "HIDDEN_PROMPT_INJECTION", "excerpt": hidden[:240], "page_ref": page_ref, "action": "hidden_span_removed_from_model_input"})
                else:
                    findings.append({"type": "HIDDEN_TEXT_SPAN_REMOVED", "excerpt": hidden[:240], "page_ref": page_ref, "action": "hidden_span_removed_from_model_input"})

            ocr_text: str | None = None
            ocr_status = "not_attempted"
            try:
                if ocr_extractor is not None:
                    ocr_text = ocr_extractor(page, page_index + 1)
                elif run_native_ocr:
                    try:
                        text_page = page.get_textpage_ocr(language="ind+eng", dpi=150, full=True)
                    except Exception:
                        text_page = page.get_textpage_ocr(language="eng", dpi=150, full=True)
                    ocr_text = page.get_text("text", textpage=text_page) or ""
                if ocr_text is not None:
                    ocr_available_count += 1
                    ocr_status = "completed"
            except Exception as exc:  # Tesseract/tessdata is an optional system dependency.
                ocr_status = "unavailable"
                LOGGER.debug("PDF OCR unavailable", extra={"page": page_index + 1, "error_type": type(exc).__name__})

            comparison = _compare_digital_and_ocr(raw_text, ocr_text) if ocr_text is not None else {
                "status": "unavailable", "digital_token_count": len(_tokens(raw_text)), "absent_token_count": None, "absent_ratio": None,
            }
            if comparison.get("visible_text_ratio") is not None and comparison["visible_text_ratio"] < 0.75:
                findings.append({
                    "type": "SUSPICIOUS_HIDDEN_PAYLOAD",
                    "page_ref": page_ref,
                    "digital_token_count": comparison["digital_token_count"],
                    "ocr_absent_token_count": comparison["absent_token_count"],
                    "ocr_absent_ratio": comparison["absent_ratio"],
                    "visible_text_ratio": comparison["visible_text_ratio"],
                    "minimum_visible_text_ratio": 0.75,
                    "comparison_basis": "PDF text layer compared with OCR of rendered page pixels",
                })

            page_result = {
                "page_ref": page_ref,
                "sanitized_text": cleaned["sanitized_text"],
                "digital_text_character_count": len(raw_text),
                "ocr_status": ocr_status,
                "ocr_comparison": comparison,
                "findings": findings,
            }
            page_results.append(page_result)
            all_findings.extend(findings)
        return {
            "status": "screened" if page_results else "empty_pdf",
            "page_count": len(page_results),
            "ocr_pages_completed": ocr_available_count,
            "findings": all_findings,
            "pages": page_results,
            "interpretation": "Perbedaan teks digital/OCR, teks putih, dan ukuran huruf hanya sinyal untuk telaah berkas asli.",
        }


def _tokens(text: str) -> list[str]:
    return [match.group(0).casefold() for match in _WORD.finditer(unicodedata.normalize("NFKC", text))]


def _compare_digital_and_ocr(digital_text: str, ocr_text: str) -> dict[str, Any]:
    digital = Counter(_tokens(digital_text))
    visible = Counter(_tokens(ocr_text))
    total = sum(digital.values())
    absent = sum(max(0, count - visible[token]) for token, count in digital.items())
    ratio = absent / total if total else 0.0
    return {
        "status": "comparison_completed",
        "digital_token_count": total,
        "ocr_token_count": sum(visible.values()),
        "absent_token_count": absent,
        "absent_ratio": round(ratio, 6),
        "visible_text_ratio": round(1.0 - ratio, 6),
        "threshold": HIDDEN_TEXT_RATIO_THRESHOLD,
    }


def _rgb(color: int) -> tuple[int, int, int]:
    return ((color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF)


def _colors_match(first: tuple[int, int, int], second: tuple[int, int, int], tolerance: int = 12) -> bool:
    return all(abs(left - right) <= tolerance for left, right in zip(first, second))


def _sample_background_color(pixmap: Any, page_rect: Any, bbox: Any) -> tuple[int, int, int] | None:
    """Sample pixels just outside a span bbox and select the most common color."""

    if pixmap is None or not isinstance(bbox, (tuple, list)) or len(bbox) != 4:
        return None
    if not getattr(pixmap, "samples", None) or pixmap.n < 3 or page_rect.width <= 0 or page_rect.height <= 0:
        return None
    x0, y0, x1, y1 = (float(value) for value in bbox)
    scale_x = pixmap.width / page_rect.width
    scale_y = pixmap.height / page_rect.height
    positions = (
        (x0 - 1, y0 - 1),
        (x1 + 1, y0 - 1),
        (x0 - 1, y1 + 1),
        (x1 + 1, y1 + 1),
    )
    samples: list[tuple[int, int, int]] = []
    pixels = pixmap.samples
    for x, y in positions:
        px = min(pixmap.width - 1, max(0, int(x * scale_x)))
        py = min(pixmap.height - 1, max(0, int(y * scale_y)))
        offset = (py * pixmap.width + px) * pixmap.n
        samples.append((pixels[offset], pixels[offset + 1], pixels[offset + 2]))
    return Counter(samples).most_common(1)[0][0] if samples else None
