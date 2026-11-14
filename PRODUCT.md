# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
- Primary: people using Analog Atlas to find Earth analogs of Moon and Mars regions: the competition team, NASA Space Apps 2026 judges, and planetary scientists or students exploring the results.
- The same people also run the data pipeline (Earth Engine extraction, merge, discovery checks, offline snapshot) without a terminal, from the **Data pipeline** drawer inside the Atlas. Confirmed by the user on 2026-11-14: the interface is `index.html` itself, globes included, and the extra code upgrades it rather than adding a separate page.

## Product Purpose
Analog Atlas turns a Moon or Mars region into a planet-independent feature vector and ranks Earth by physical similarity (SI, 0–100). Every result says what is similar, where the analogy breaks, which sources back it, and what Earth cannot reproduce. Success means a jury can verify the method on known analogs (Anchor) and see credible new candidates, preferably in the Global South (Discover).

## Positioning
- Fixed physical normalisation and weighted RMS distance; never cosine, never catalog-relative scaling.
- Validation anchors were frozen before the first run.
- The Global South is a priority (bounded point bonuses, only when SI ≥ 60), never a filter.
- Proxy data is labelled PROXY everywhere.

## Operating Context
- The frontend is a single HTML file (`index.html`): a CesiumJS globe with Trek LOD imagery and a Web Worker engine.
- The backend is Python (FastAPI plus a CLI). Earth data comes from Google Earth Engine, run on a team member's Windows machine.
- Submission closes on Sunday 15 November 2026 at 23:59 local time; code freezes at 12:00 the same day.

## Capabilities and Constraints
- Must work offline: when the API is down, the demo falls back to the local engine and an embedded snapshot.
- Single-file HTML deliverables, no build step.
- `features.json` is the single source of truth for the feature set.
- The decisions in HANDOFF_PROMPT.md §5 are fixed.
- Panel language: English (assumed; the user did not answer, and the app and judges are English).

## Brand Commitments
- Name: "Analog Atlas".
- Logo: the photographic Earth/Mars/Moon mark in `brand/`. Do not recolour, crop, outline or shadow it (`brand/README.md`).
- No NASA logos or insignia.

## Evidence on Hand
- 16 literature catalog sites and 87 APA references (embedded in `index.html`).
- 41 cited analog field campaigns (`backend/data/campaigns.csv`).
- Validation results (`python -m analog_atlas.cli validate`).
- The global Earth grid does not exist yet: discoveries must never be shown as real until the Earth Engine extraction is done.

## Product Principles
1. Honesty first: show SI next to every bonus, label proxies, and never fabricate discoveries.
2. Anchor before Discover: prove the method on known analogs, then show new places.
3. Priority, not filter: no country is ever removed.
4. Works without the network: the demo must survive a dead API.
