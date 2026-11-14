"""Inject (or update) the small judge-facing fixes of tools/polish.html into index.html. Idempotent.

    python tools/add_polish.py        (last step: after tools/add_pipeline.py)

Fixes: phone layout of the Run match button; a "Loading planetary imagery…" pill while globe tiles arrive.
"""
import re
from pathlib import Path

root = Path(__file__).resolve().parent.parent
html_path = root / "index.html"
s = html_path.read_text(encoding="utf-8")
src = (root / "tools" / "polish.html").read_text(encoding="utf-8")
part = lambda name: re.search(rf"<!--{name}-->\n(.*?)<!--/{name}-->", src, re.S).group(1)  # noqa: E731

css, script = part("CSS"), part("SCRIPT")
css_re = re.compile(r"/\* ===== POLISH \(tools/polish\.html\) ===== \*/.*?/\* ===== /POLISH ===== \*/\n", re.S)
js_re = re.compile(r"<script>\n/\* ===== POLISH: .*?</script>\n", re.S)

if css_re.search(s):
    s = css_re.sub(lambda m: css, s, count=1)
else:
    i = s.find("</style>")
    s = s[:i] + css + s[i:]
if js_re.search(s):
    s = js_re.sub(lambda m: script, s, count=1)
else:
    i = s.rfind("</body>")
    s = s[:i] + script + s[i:]

html_path.write_text(s, encoding="utf-8")
print(f"polish applied to index.html ({len(s):,} bytes)")
