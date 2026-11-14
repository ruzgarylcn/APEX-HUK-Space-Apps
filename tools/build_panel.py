"""Build panel.html from tools/panel_template.html, reusing index.html's stylesheet, icon sprite and logo,
so the pipeline panel always shares the Atlas design system.   python tools/build_panel.py"""
import re
from pathlib import Path

root = Path(__file__).resolve().parent.parent
app = (root / "index.html").read_text(encoding="utf-8")
tpl = (root / "tools" / "panel_template.html").read_text(encoding="utf-8")

style = app[app.find("<style>"): app.find("</style>") + len("</style>")]
i = app.find('<svg width="0" height="0" style="position:absolute" aria-hidden="true">')
sprite = app[i: app.find("</svg>", app.rfind("</symbol>")) + len("</svg>")]
favicon = re.search(r'<link rel="icon"[^>]*/>', app).group(0)
logo = re.search(r'<span class="brand-mark"><img src="(data:image/png;base64,[^"]+)"', app).group(1)
assert style and sprite.startswith("<svg") and "</symbol>" in sprite

out = (tpl.replace("{{STYLE}}", style).replace("{{SPRITE}}", sprite)
          .replace("{{FAVICON}}", favicon).replace("{{LOGO96}}", logo))
assert "{{" not in out
(root / "panel.html").write_text(out, encoding="utf-8")
print(f"panel.html written ({len(out):,} bytes)")
