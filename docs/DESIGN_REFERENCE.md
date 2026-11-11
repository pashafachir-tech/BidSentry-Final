# UI design reference audit

## What the supplied archive contains

`ui_lovelace_minimalist.zip` contains Home Assistant integration `ui_lovelace_minimalist` v1.5.8, not a React/Vue website, Tailwind theme, or CSS module library. Its core design files are Lovelace YAML dashboards and theme variables. The archive declares Home Assistant dependencies (`lovelace`, `http`, `frontend`) plus Python requirements for its integration. It also includes bundled custom-card JavaScript; those files are not used by BidSentry.

## Design cues applied to BidSentry

- Warm near-white canvas, white surfaces, thin dividers, and restrained shadows.
- Compact status colors for success, warning, and risk signals; color is paired with text labels.
- Rounded cards and controls, with generous spacing around section titles.
- A simple dashboard composed of metric cards, a dense register table, and a focused detail panel.
- Responsive navigation and a one-column layout on narrow screens.
- No third-party CSS or icon runtime; styling and inline icons are served locally.

The extracted archive is retained at `output/template-reference/ui_lovelace_minimalist/` for inspection. Home Assistant YAML and bundled scripts are reference material only; no archive instructions or runtime code are imported into the web application.
