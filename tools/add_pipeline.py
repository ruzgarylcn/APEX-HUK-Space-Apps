"""Upgrade index.html in place: data-pipeline drawer (runs the backend pipeline from inside the Atlas) and automatic
detection of the local API, so discoveries go live when the Atlas is opened through start.bat. Idempotent.

    python tools/add_pipeline.py            (after brand/apply_logo.py)
"""
import re
from pathlib import Path

root = Path(__file__).resolve().parent.parent
html_path = root / "index.html"
s = html_path.read_text(encoding="utf-8")
src = (root / "tools" / "pipeline_drawer.html").read_text(encoding="utf-8")
part = lambda name: re.search(rf"<!--{name}-->\n(.*?)<!--/{name}-->", src, re.S).group(1)  # noqa: E731

if 'id="pp-drawer"' in s:
    # Update mode: swap the drawer's own segments for the current source; module patches stay as they are.
    def swap(pattern, new):
        global s
        s, n = re.subn(pattern, lambda m: new, s, count=1, flags=re.S)
        assert n == 1, pattern
    swap(r'    <symbol id="i-pipeline".*?</symbol>\n', part("ICON"))
    swap(r'      <button class="icon-btn" id="pp-open".*?</button>\n', part("BUTTON"))
    swap(r'/\* ===== DATA PIPELINE DRAWER .*?(?=</style>)', part("CSS"))
    swap(r'<!-- ===== DATA PIPELINE DRAWER ===== -->.*?(?=<div id="tooltip")', part("MARKUP"))
    swap(r'<script>\n/\* ===== DATA PIPELINE DRAWER.*?</script>\n', part("SCRIPT"))
    # Judge-facing status text (static hosting such as GitHub Pages has no start.bat): migrate older builds.
    s = s.replace("(Object.keys(OFFLINE_RESULTS).length ? 'Discoveries: offline snapshot' : 'Discoveries: start.bat for live')",
                  "(Object.keys(OFFLINE_RESULTS).length ? `Discoveries: offline snapshot (${Object.keys(OFFLINE_RESULTS).length} entries)` : 'Discoveries: not available offline')")
    html_path.write_text(s, encoding="utf-8")
    raise SystemExit(f"pipeline drawer updated in index.html ({len(s):,} bytes)")


def rep(old, new):
    global s
    assert s.count(old) == 1, f"anchor not unique: {old[:70]!r}"
    s = s.replace(old, new)


# icon into the sprite, button into the top bar, CSS, drawer markup, drawer script
end_sprite = s.find("  </defs>\n</svg>", s.rfind("</symbol>", 0, s.find('<div id="app"')))
s = s[:end_sprite] + part("ICON") + s[end_sprite:]
rep('<div class="top-actions">\n', '<div class="top-actions">\n' + part("BUTTON"))
i = s.find("</style>")
s = s[:i] + part("CSS") + s[i:]
rep('<div id="tooltip" role="tooltip"></div>', part("MARKUP") + '<div id="tooltip" role="tooltip"></div>')
i = s.rfind("</body>")
s = s[:i] + part("SCRIPT") + s[i:]

# status bar: where discoveries come from
rep('<span class="status-credit">', '<span class="status-item mono" id="api-chip" data-tip="Where New discoveries come from">Discoveries: checking…</span>\n    <span class="status-credit">')

# module: find the local API automatically (same origin as start.bat serves), then use it for discoveries
rep("let OFFLINE_RESULTS = {};", """let OFFLINE_RESULTS = {};
// The local server (start.bat) serves this page and the API on one origin: use it without ?api=.
let API_ORIGIN = CONFIG.API_BASE;
const apiReady = (async () => {
  if (!API_ORIGIN && location.protocol.startsWith('http')) {
    const ctl = new AbortController(), t = setTimeout(() => ctl.abort(), 1500);
    try { const r = await fetch(location.origin + '/health', { signal: ctl.signal }); if (r.ok && (await r.json()).ok) API_ORIGIN = location.origin; }
    catch (e) { /* static hosting or offline: stay local */ }
    clearTimeout(t);
  }
  const chip = document.getElementById('api-chip');
  if (chip) chip.textContent = API_ORIGIN ? 'Discoveries: live API' : (Object.keys(OFFLINE_RESULTS).length ? `Discoveries: offline snapshot (${Object.keys(OFFLINE_RESULTS).length} entries)` : 'Discoveries: not available offline');
})();""")
rep("    if (CONFIG.API_BASE) {", "    await apiReady;\n    if (API_ORIGIN) {")
rep("CONFIG.API_BASE.replace(/\\/$/, '') + '/find-analogs'", "API_ORIGIN.replace(/\\/$/, '') + '/find-analogs'")

html_path.write_text(s, encoding="utf-8")
print(f"index.html upgraded ({len(s):,} bytes)")
