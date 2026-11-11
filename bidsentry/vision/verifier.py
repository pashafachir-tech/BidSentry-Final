"""Conservative signature, stamp and e-Meterai artifact signal review."""

from __future__ import annotations

from typing import Any

from bidsentry.schemas.comprehensive import ArtifactSignal


def verify_artifacts(
    signals: list[ArtifactSignal],
    page_visual_inventory: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    supplied_keys: set[tuple[str, str | None]] = set()
    for signal in signals:
        supplied_keys.add((signal.artifact_type, signal.page_ref))
        if signal.detected is False:
            status = "NOT_DETECTED"
            notes = ["Pemindai tidak melaporkan artefak pada halaman ini; ini bukan bukti artefak tidak ada."]
        else:
            notes = []
            if signal.artifact_type == "SIGNATURE" and signal.alpha_layer:
                notes.append("Alpha/soft-mask ditemukan pada sinyal visual; dapat menandakan objek gambar overlay dan perlu pemeriksaan berkas asli.")
            if signal.artifact_type == "SIGNATURE" and signal.dpi is not None and signal.dpi < 150:
                notes.append("Resolusi raster di bawah 150 DPI dilaporkan; ini bukan bukti pemalsuan.")
            if signal.artifact_type == "SIGNATURE" and signal.vector_paths:
                notes.append("Jalur vektor terdeteksi; keberadaan vektor tidak membuktikan tanda tangan digital tersertifikasi.")
            if signal.artifact_type == "E_METERAI" and signal.certified_signature is not True:
                notes.append("Status sertifikat/tanda tangan digital belum tervalidasi secara kriptografis.")
            if signal.description:
                notes.append(signal.description)
            if signal.detected is True and signal.artifact_type == "SIGNATURE" and signal.alpha_layer:
                status = "SUSPICIOUS_RASTER_OVERLAY_SIGNAL"
            elif signal.detected is True and signal.certified_signature is True:
                status = "CERTIFICATE_VALIDITY_REPORTED_NOT_VERIFIED"
            elif signal.detected is True:
                status = "DETECTED_UNVERIFIED"
            else:
                status = "UNVERIFIABLE"
        findings.append({
            "artifact_type": signal.artifact_type,
            "status": status,
            "page_ref": signal.page_ref,
            "signals": notes,
            "human_review_required": status != "NOT_DETECTED",
        })
    automatic_candidate_count = 0
    for page in page_visual_inventory or []:
        page_ref = str(page.get("page_ref") or "") or None
        for candidate in page.get("artifact_candidate_regions", []):
            artifact_type = str(candidate.get("artifact_type") or "")
            if artifact_type not in {"SIGNATURE", "STAMP", "E_METERAI"}:
                continue
            if (artifact_type, page_ref) in supplied_keys:
                continue
            nearby_images = candidate.get("nearby_images", [])
            has_image = bool(candidate.get("nearby_image_count", len(nearby_images)))
            has_soft_mask = any(image.get("has_soft_mask") is True for image in nearby_images if isinstance(image, dict))
            reported_dpis = [
                dpi
                for image in nearby_images if isinstance(image, dict)
                for dpi in (image.get("dpi_x"), image.get("dpi_y"))
                if isinstance(dpi, (int, float)) and dpi > 0
            ]
            low_resolution = any(dpi < 150 for dpi in reported_dpis)
            drawing_count = int(candidate.get("nearby_vector_drawing_count") or 0)
            notes = [f"Label '{candidate.get('anchor_label', 'artefak')}' ditemukan pada lapisan teks PDF."]
            if has_image:
                notes.append(f"{candidate.get('nearby_image_count', len(nearby_images))} objek raster ditemukan dalam radius 180 pt.")
            if has_soft_mask:
                notes.append("Objek terdekat memiliki soft mask/transparansi; ini hanya sinyal visual, bukan bukti overlay palsu.")
            if low_resolution:
                notes.append("Objek raster terdekat memiliki resolusi efektif di bawah 150 DPI.")
            if drawing_count:
                notes.append(f"{drawing_count} objek vektor ditemukan dekat label.")
            if not has_image and not drawing_count:
                notes.append("Tidak ada objek raster atau vektor yang berdekatan pada inventaris halaman.")
            if artifact_type == "SIGNATURE" and has_image and has_soft_mask:
                status = "SUSPICIOUS_RASTER_OVERLAY_SIGNAL"
            elif has_image or drawing_count:
                status = "POTENTIAL_VISUAL_ARTIFACT_REVIEW"
            else:
                status = "TEXTUAL_ARTIFACT_ANCHOR_ONLY"
            findings.append({
                "artifact_type": artifact_type,
                "status": status,
                "page_ref": page_ref,
                "signals": notes,
                "evidence": {
                    "anchor_label": candidate.get("anchor_label"),
                    "nearby_image_count": candidate.get("nearby_image_count", len(nearby_images)),
                    "nearby_images": nearby_images[:10],
                    "nearby_vector_drawing_count": drawing_count,
                },
                "human_review_required": True,
                "automatically_detected": True,
            })
            automatic_candidate_count += 1
    return {
        "status": "screened" if signals or automatic_candidate_count else ("graphics_inventory_only" if page_visual_inventory else "no_vision_data"),
        "findings": findings,
        "automatic_candidate_count": automatic_candidate_count,
        "pdf_graphics_inventory": page_visual_inventory or [],
        "graphics_inventory_note": "Skrining otomatis menghubungkan label artefak pada text layer ke objek raster/vektor terdekat dan menandai transparansi/resolusi. Skrining ini tidak melakukan OCR atau klasifikasi piksel.",
        "physical_stamp_verified": False,
        "signature_authenticity_verified": False,
        "meterai_cryptographically_verified": False,
        "limitation": "Label memerlukan text layer yang terbaca; PDF hasil scan tanpa OCR dapat luput. Kedekatan objek tidak mengenali tanda tangan/stempel dari piksel dan tidak membuktikan keaslian fisik atau e-Meterai. Verifikasi sertifikat memerlukan validasi kriptografis dan/atau pemeriksaan alat resmi.",
    }
