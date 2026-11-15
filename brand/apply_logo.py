"""Put the Analog Atlas logo into the single-file app (index.html): favicon + top-bar mark.

Usage (from the project root):  python brand/apply_logo.py index.html
Embeds small PNGs as data URIs so the app stays a single, offline-capable file.
Safe to run twice: it replaces whatever favicon / top-bar mark is there.
"""
import base64
import io
import re
import sys
from pathlib import Path

from PIL import Image

html_path = Path(sys.argv[1])
mark = Image.open(Path(__file__).with_name("analog-atlas-mark.png")).convert("RGBA")

def data_uri(size):
    buf = io.BytesIO()
    mark.resize((size, size), Image.LANCZOS).save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

s = html_path.read_text(encoding="utf-8")
n_before = len(s)

# 1) favicon
s, n1 = re.subn(r'<link rel="icon"[^>]*/>', f'<link rel="icon" type="image/png" href="{data_uri(64)}" />', s, count=1)

# 2) top-bar mark: replace the icon inside .brand-mark with the logo image
s, n2 = re.subn(r'<span class="brand-mark">.*?</span>',
                f'<span class="brand-mark"><img src="{data_uri(96)}" alt="" width="34" height="34" /></span>',
                s, count=1, flags=re.S)

# 3) CSS: the logo is the badge itself — drop the glowing tile behind it
css_old = re.search(r"\.brand-mark\{width:34px;height:34px;.*?\}\s*\.brand-mark svg\{width:22px;height:22px\}", s, re.S)
n3 = 0
if css_old:
    s = s.replace(css_old.group(0),
                  ".brand-mark{width:34px;height:34px;flex:none;display:grid;place-items:center}\n"
                  ".brand-mark img{width:34px;height:34px;display:block;filter:drop-shadow(0 0 10px color-mix(in srgb,var(--glow-a) 30%,transparent))}")
    n3 = 1
elif ".brand-mark img{" in s:
    n3 = 1   # already applied

if not (n1 and n2 and n3):
    sys.exit(f"Nothing changed safely (favicon={n1}, topbar={n2}, css={n3}); check the file by hand.")
html_path.write_text(s, encoding="utf-8")
print(f"Logo applied: favicon, top-bar mark, CSS. Size {n_before:,} -> {len(s):,} bytes.")
