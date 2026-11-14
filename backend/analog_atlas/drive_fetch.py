"""Download Earth Engine export CSVs from the user's Google Drive into data/exports/ (no manual download).

Uses the credentials saved by `earthengine authenticate` (they include the Drive scope that Earth Engine
exports already need). Read-only: lists and downloads files; never deletes or edits anything on Drive.

    python -m analog_atlas.drive_fetch [--folder analog_atlas] [--prefix analog_atlas_50km_]
"""
from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

from .config import DATA_DIR


def _drive():
    import ee
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials(None, **ee.oauth.get_credentials_arguments())   # token=None: refreshed from the saved refresh token
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def fetch(folder: str = "analog_atlas", prefix: str = "analog_atlas_50km_", out_dir: Path | None = None) -> list[Path]:
    from googleapiclient.http import MediaIoBaseDownload

    out_dir = Path(out_dir or DATA_DIR / "exports")
    out_dir.mkdir(parents=True, exist_ok=True)
    svc = _drive()
    folders = svc.files().list(q=f"name = '{folder}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
                               fields="files(id, name)").execute().get("files", [])
    if not folders:
        print(f"Drive folder '{folder}' not found yet (it appears when the first export task finishes).")
        return []
    got = []
    for fd in folders:
        q = f"'{fd['id']}' in parents and name contains '{prefix}' and trashed = false"
        files = svc.files().list(q=q, fields="files(id, name, size, modifiedTime)", pageSize=200).execute().get("files", [])
        for f in sorted(files, key=lambda x: x["name"]):
            if not f["name"].endswith(".csv"):
                continue
            target = out_dir / f["name"]
            if target.exists() and str(target.stat().st_size) == f.get("size"):
                got.append(target)
                continue
            buf = io.BytesIO()
            dl = MediaIoBaseDownload(buf, svc.files().get_media(fileId=f["id"]))
            done = False
            while not done:
                _, done = dl.next_chunk()
            target.write_bytes(buf.getvalue())
            print(f"downloaded {f['name']} ({int(f.get('size', 0)):,} bytes)")
            got.append(target)
    print(f"{len(got)} CSV file(s) in {out_dir}")
    return got


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--folder", default="analog_atlas")
    p.add_argument("--prefix", default="analog_atlas_50km_")
    a = p.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    fetch(a.folder, a.prefix)


if __name__ == "__main__":
    main()
