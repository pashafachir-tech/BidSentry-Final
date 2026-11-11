# UI assets and reference provenance

## Generated BidSentry screenshots

The screenshots below were captured from the local app with synthetic fixtures. The register and risk detail images include one browser-generated test audit; they do not contain real procurement data.

Screenshot PNGs are delivered as workspace assets under `output/`; they are separate from the application source ZIP.

- `output/bidsentry-dashboard.png` — executive overview, sample procurement register, selected package risk rating, risk distribution, and integration status.
- `output/bidsentry-dashboard-pitch.png` — wide dashboard capture framed for a 16:9 slide.
- `output/bidsentry-mobile.png` — responsive dashboard at a 390 px viewport.
- `output/bidsentry-audit-register.png` — search/filter controls and the procurement audit register with risk badges and scores.
- `output/bidsentry-risk-detail.png` — selected audit's score, risk band, findings, and follow-up action.
- `output/bidsentry-audit-deep-dive.png` — complete dashboard after an audit scan.

The refactored app does not expose a separate raw audit-log screen. Its JSONL log is metadata-only at the configured `AUDIT_LOG_PATH`; reviewers use the audit register and risk detail in the UI. A screenshot from the previous UI/log format is retained at `output/archive/pre-refactor/assets/ui_audit_log.png` and is historical reference only.

## Supplied design reference

The uploaded `ui_lovelace_minimalist.zip` is the Home Assistant `ui_lovelace_minimalist` integration (v1.5.8), not a Tailwind or CSS Modules component library. Its YAML dashboard cards, theme colors, typography choices, and spacing were reviewed for visual cues. The ZIP was extracted for reference to `output/template-reference/ui_lovelace_minimalist/`; no archive code or YAML is imported by BidSentry.

The app implements those cues in its own local CSS: a warm neutral canvas, dark ink text, muted status colors, fine borders, rounded cards, compact labels, and editorial serif headings. See `web/styles.css` for the tokens and styles.
