"""Apply tools/extra_refs.json to the catalog and the frontend (idempotent; run from the repository root).

- appends missing citations to index.html #citation-db
- sets per-site fields (source_ids, rocks, description) in backend/data/catalog_sites.json and index.html #analog-db
- updates the "N references / sources" counts shown in index.html and README.md

Only non-scored fields are touched, so similarity scores and the frozen validation do not change.

    python tools/add_refs.py
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXTRA = json.loads((ROOT / "tools" / "extra_refs.json").read_text(encoding="utf-8"))
ALLOWED = {"source_ids", "rocks", "description"}


def block(html, bid):
    m = re.search(r'(<script type="application/json" id="%s">)(.*?)(</script>)' % bid, html, re.S)
    if not m:
        raise SystemExit(f"#{bid} not found in index.html")
    return m


def patch_sites(sites):
    for s in sites:
        for k, v in EXTRA["sites"].get(s["id"], {}).items():
            if k not in ALLOWED:
                raise SystemExit(f"refusing to change scored field {k!r}")
            s[k] = v
    return sites


def main():
    # backend catalog: indent=1, CRLF, no trailing newline (the original file's format)
    cat_path = ROOT / "backend" / "data" / "catalog_sites.json"
    cat = patch_sites(json.loads(cat_path.read_text(encoding="utf-8")))
    cat_path.write_bytes(json.dumps(cat, ensure_ascii=False, indent=1).replace("\n", "\r\n").encode("utf-8"))

    html_path = ROOT / "index.html"
    html = html_path.read_bytes().decode("utf-8")   # bytes: keep line endings exactly

    m = block(html, "analog-db")
    sites = patch_sites(json.loads(m.group(2)))
    html = html[:m.start(2)] + "\n" + json.dumps(sites, ensure_ascii=False) + "\n" + html[m.end(2):]

    m = block(html, "citation-db")
    cites = json.loads(m.group(2))
    have = {c["id"] for c in cites}
    new = [c for c in EXTRA["citations"] if c["id"] not in have]
    body = m.group(2).rstrip()
    if new:
        assert body.endswith("]")
        body = body[:-1] + "".join("," + json.dumps(c, ensure_ascii=False, separators=(",", ":")) for c in new) + "]"
    html = html[:m.start(2)] + body + "\n" + html[m.end(2):]
    n = len(cites) + len(new)

    for pat, rep in [(r"All \d+ dataset references", f"All {n} dataset references"),
                     (r"lists all \d+ sources", f"lists all {n} sources"),
                     (r"Dataset · \d+ sources", f"Dataset · {n} sources")]:
        html = re.sub(pat, rep, html)
    html_path.write_bytes(html.encode("utf-8"))

    readme = ROOT / "README.md"
    readme.write_bytes(re.sub(r"The \d+ references are listed", f"The {n} references are listed",
                              readme.read_bytes().decode("utf-8")).encode("utf-8"))
    print(f"{len(new)} citation(s) added, {n} in total; sites patched: {', '.join(EXTRA['sites'])}")


if __name__ == "__main__":
    main()
