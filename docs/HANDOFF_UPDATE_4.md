# Handoff update #4 — new logo (paste to Claude)

The team picked the **photographic** version of the new logo. Copy this zip's `brand/` folder into the project root
(next to `p2.html`), then run from the project root:

```bash
python brand/apply_logo.py p2.html
```

What the script does (it is safe to run twice):
- **Browser-tab icon:** Replaces the favicon with the logo, embedded as a 64 px PNG data URI. The app stays one offline file.
- **Top-bar logo:** Replaces the top-bar mark (the `.brand-mark` span next to "ANALOG ATLAS") with the logo, 96 px embedded, shown at 34 px.
- **CSS:** Removes the glowing tile behind the mark and adds a soft glow in the current theme colour.
- **Size:** Adds about 37 KB to `p2.html`.

**Already tested:** Applied to a copy of the current `p2.html`, run twice. The page loaded with no console errors, the logo image showed in the top bar at 34×34 px, and the favicon changed.

**Other places to use the logo:**
- **README:** Put `brand/analog-atlas-mark-256.png` at the top.
- **GitHub social preview:** Use `brand/analog-atlas-lockup-dark.png`.
- **Slide deck:** The cover slide already uses it.
- **Do not** recolour or crop the logo, or add outlines. See `brand/README.md`.

**References field (submission page):**
- **Image sources:** Add the sources of the Earth, Mars and Moon photos used in the team's logo collage.
- **AI-use field:** The logo was cleaned up with AI-assisted image-processing code, not a generative image model.
