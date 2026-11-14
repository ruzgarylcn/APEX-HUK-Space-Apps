"""Inject the NASA-style theme (tools/theme_nasa.css) into index.html (idempotent; run from the repository root, last).

Visual only: it overrides CSS variables and styles, strips the emoji from the body tabs and colours each
similarity ring by score band (>=75 strong, >=60 good, else partial). Engine, data and scores are untouched.
Re-running replaces the block between the markers, so edit tools/theme_nasa.css, not index.html.

    python tools/add_theme.py
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "tools" / "theme_nasa.css").read_text(encoding="utf-8").strip()

HEAD = ("<!-- nasa-theme:head -->\n"
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;800'
        '&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">\n'
        f'<style id="nasa-theme">\n{CSS}\n</style>\n'
        "<!-- /nasa-theme:head -->\n")

BODY = r"""<!-- nasa-theme:body -->
<script id="nasa-theme-js">
// drop the emoji glyphs from the body tabs (text nodes only; the labels stay)
document.querySelectorAll('#body-switcher .tab').forEach((t) => t.childNodes.forEach((n) => { if (n.nodeType === 3) n.textContent = ' '; }));
// colour each similarity ring by its score band
(function () {
  const band = (w) => {
    const m = /(\d+(?:\.\d+)?) percent/.exec(w.getAttribute('aria-label') || '');
    if (!m) return;
    const v = +m[1], t = v >= 75 ? 'strong' : v >= 60 ? 'good' : 'partial';
    if (w.dataset.band !== t) w.dataset.band = t;
  };
  const run = () => document.querySelectorAll('.si-wrap').forEach(band);
  new MutationObserver(run).observe(document.body, { childList: true, subtree: true });
  run();
})();
</script>
<!-- /nasa-theme:body -->
"""


def put(html, tag, close, block):
    pat = re.compile(r"<!-- nasa-theme:%s -->.*?<!-- /nasa-theme:%s -->\r?\n" % (tag, tag), re.S)
    if pat.search(html):
        return pat.sub(lambda _: block, html, count=1)
    i = html.rindex(close)
    return html[:i] + block + html[i:]


def main():
    path = ROOT / "index.html"
    raw = path.read_bytes().decode("utf-8")          # bytes: keep line endings exactly
    nl = "\r\n" if raw.count("\r\n") > raw.count("\n") / 2 else "\n"
    html = put(raw, "head", "</head>", HEAD.replace("\n", nl))
    html = put(html, "body", "</body>", BODY.replace("\n", nl))
    path.write_bytes(html.encode("utf-8"))
    print("theme injected" if html != raw else "theme already up to date")


if __name__ == "__main__":
    main()
