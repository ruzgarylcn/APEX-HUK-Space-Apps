# START HERE — complete project package (paste this whole file to Claude first)

> **Update #5 (2026-11-14):** the deliverable frontend is now **`index.html`** (p2 engine + Cesium LOD globe + new
> logo + Anchor & Discover). `p2.html` is in `archive/`; the logo is already applied. Backend: 29 tests.
> What changed and why: `docs/HANDOFF_UPDATE_5.md`. Earth Engine steps: `docs/RUN_EARTH_ENGINE.md`.

This zip is the **complete, current project**. It replaces every earlier zip (the handoff zip and updates #2, #3 and #4).
The team member who received only "update 3" was missing most of the project. This package fixes that.

## 1. Read the context first
1. Read **`HANDOFF_PROMPT.md`** in full. It holds the challenge, the architecture, the **non-negotiable decisions** and the task plan.
2. Then read `docs/HANDOFF_UPDATE_2.md`, `docs/HANDOFF_UPDATE_3.md` and `docs/HANDOFF_UPDATE_4.md`, in that order. Their changes are already applied in this zip; read them only to know what changed and why.

## 2. If work was already done from the "update 3" zip alone
Before unpacking, check what exists in the current working folder.

- **Files that came from "update 3" and were not edited:** Discard them. This zip has the same versions.
- **Core files Claude re-created because they were missing:** Do **not** keep them. Use this zip's versions; those are the tested engine. This covers `scoring.py`, `features.py`, `priority.py`, `config.py`, `grid.py`, `countries.py`, `api.py`, `extract/earth_gee.py`, any JSON config and `p2.html`. A re-created engine may differ in ways that break the frozen validation, e.g. cosine similarity, catalog-relative normalisation or a different priority formula.
- **Genuinely new work:** Keep it, but merge it into this zip's files rather than replacing them. Examples: Earth Engine fixes, a `merge-exports` command, a `campaigns`-based novelty layer, frontend–API wiring.
  - Diff your version against this zip's version and port only your additions.
  - Run the tests after each merge.
- **If unsure:** Unpack this zip into a **new folder**, re-apply your own additions there, and switch to that folder.

## 3. Verify the package (all of this was run on 2026-11-14 in a clean folder and passed)
From `backend/`:

```bash
pip install numpy pandas pyarrow requests
```

```bash
python -m unittest discover -s tests -v
```

**16 tests** should pass.

```bash
python -m analog_atlas.cli validate
```

Expected hit@5: 1.0 for landing / resource / habitat and 0.8 for science.

```bash
python -m analog_atlas.cli demo --target jezero --profile science --top 3
```

Lake Salda should be #1.

From the project root:

```bash
python brand/apply_logo.py p2.html
```

This puts the new logo into the app. It is safe to run twice.

## 4. Then continue with the plan
Continue with step B (Earth Engine) in `HANDOFF_PROMPT.md`.

**The deadline is earlier than first planned:** submission closes **Sunday 15 November 2026, 23:59 local time** of the team's Local Event. Freeze the code by **Sunday 12:00**.

## Contents
| Path | What |
|---|---|
| `p2.html` | Frontend (single file) |
| `HANDOFF_PROMPT.md` | Full context and plan (read first) |
| `backend/` | Engine, priority layer, validation, discovery check, Earth Engine extraction, API, 16 tests |
| `backend/data/campaigns.csv` | 41 cited analog field campaigns (novelty layer + slide data) |
| `backend/config/discovery_checklist.json` | Frozen discovery test (10 candidates, Jingpo flagged) |
| `brand/` | Logo files + `apply_logo.py` |
| `docs/` | Update notes and `campaigns_summary.md` (slide numbers) |
