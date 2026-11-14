"""Local control server: the Analog Atlas API + the pipeline panel + the app, on one port.

    python -m uvicorn analog_atlas.server:app --host 127.0.0.1 --port 8000      (or double-click start.bat)

GET  /                     panel.html (pipeline control panel)
GET  /index.html           the Analog Atlas app (open it with ?api=<this origin> for live discoveries)
GET  /panel/status         data files, grid size, offline snapshot, saved Earth Engine project
POST /panel/config         {"project": "<gcp project id>"}
POST /jobs                 {"action": "<whitelisted action>", "params": {...}}   one job at a time
GET  /jobs                 job history
GET  /jobs/{id}?since=N    log lines from N on + state
POST /jobs/{id}/cancel
POST /exports/upload?name= raw CSV body -> backend/data/exports/<name>
+ every route of analog_atlas.api (/health, /targets, /config, /score, /find-analogs)

Jobs run the CLI (python -m analog_atlas.cli ...) in a subprocess; only the actions below are allowed and every
parameter is validated, so the panel can never run an arbitrary command. Bind to 127.0.0.1 only.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .api import app
from .config import DATA_DIR, features_config, targets

BACKEND_DIR = DATA_DIR.parent
ROOT_DIR = BACKEND_DIR.parent
EXPORTS_DIR = DATA_DIR / "exports"
PANEL_CFG = BACKEND_DIR / ".panel.json"
PROJECT_RE = re.compile(r"^[a-z][a-z0-9-]{4,61}[a-z0-9]$")      # Google Cloud project id rules
CSV_NAME_RE = re.compile(r"^[A-Za-z0-9._ ()-]{1,120}\.csv$")


# ----------------------------------------------------------------------------- actions (whitelist)
def _cli(*args: str) -> list[str]:
    return [sys.executable, "-u", "-m", "analog_atlas.cli", *args]


def _project(p: dict) -> str:
    project = str(p.get("project") or _load_cfg().get("project") or "")
    if not PROJECT_RE.match(project):
        raise HTTPException(422, "Set a valid Google Cloud project ID first (lowercase letters, digits, hyphens).")
    return project


def _choice(p: dict, key: str, allowed, default: str) -> str:
    v = str(p.get(key) or default)
    if v not in allowed:
        raise HTTPException(422, f"{key} must be one of {sorted(allowed)}")
    return v


def _plan(action: str, p: dict) -> tuple[str, list[list[str]]]:
    """(label, command list) for a whitelisted action."""
    target_ids = {t["id"] for t in targets()}
    profiles = set(features_config()["profiles"])
    if action == "tests":
        return "Run the test suite", [[sys.executable, "-u", "-m", "unittest", "discover", "-s", "tests", "-v"]]
    if action == "auth":
        return "Sign in to Earth Engine", [[sys.executable, "-u", "-c",
                                            "import ee; ee.Authenticate(force=True, auth_mode='localhost'); print('Earth Engine credentials saved.')"]]
    if action == "smoke":
        pr = _project(p)
        return "Smoke test: Türkiye box, 25 km", [_cli("build-grid", "--km", "25", "--bbox", "26", "36", "31", "39", "--countries"),
                                                   _cli("extract-earth", "--project", pr, "--mode", "sample")]
    if action == "export":
        pr = _project(p)
        extra = ["--no-s2"] if p.get("no_s2", True) else []
        return "Global export: 50 km land grid", [_cli("build-grid", "--km", "50", "--countries"),
                                                   _cli("extract-earth", "--project", pr, "--mode", "export", *extra)]
    if action == "export_status":
        return "Earth Engine task status", [_cli("export-status", "--project", _project(p))]
    if action == "merge":
        return "Merge exported CSVs", [_cli("merge-exports", "--dir", str(EXPORTS_DIR))]
    if action == "validate":
        return "Validate frozen anchors", [_cli("validate")]
    if action == "find":
        t = _choice(p, "target", target_ids, "cerberus")
        pf = _choice(p, "profile", profiles, "science")
        return f"Anchor & Discover: {t} · {pf}", [_cli("find", "--target", t, "--profile", pf)]
    if action == "check":
        return "Frozen discovery checklist", [_cli("check-discoveries")]
    if action == "offline":
        return "Embed offline snapshot into index.html", [_cli("export-offline", "--embed", str(ROOT_DIR / "index.html"))]
    if action == "dois":
        return "Verify reference DOIs on Crossref", [_cli("verify-dois", "--html", str(ROOT_DIR / "index.html"))]
    raise HTTPException(404, f"unknown action '{action}'")


# ----------------------------------------------------------------------------- job runner
class Job:
    def __init__(self, action: str, label: str, commands: list[list[str]]):
        self.id = uuid.uuid4().hex[:10]
        self.action, self.label, self.commands = action, label, commands
        self.lines: list[str] = []
        self.state = "running"            # running | done | failed | cancelled
        self.returncode: int | None = None
        self.started, self.ended = time.time(), None
        self.proc: subprocess.Popen | None = None
        self.cancelled = False
        self.lock = threading.Lock()

    def log(self, text: str) -> None:
        with self.lock:
            self.lines.append(text.rstrip("\r\n"))

    def summary(self) -> dict:
        return {"id": self.id, "action": self.action, "label": self.label, "state": self.state,
                "returncode": self.returncode, "started": self.started, "ended": self.ended, "lines": len(self.lines)}


JOBS: dict[str, Job] = {}
ORDER: list[str] = []
_runner_lock = threading.Lock()


def _run(job: Job) -> None:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
    try:
        for cmd in job.commands:
            shown = " ".join(c if c != sys.executable else "python" for c in cmd)
            job.log(f"$ {shown}")
            job.proc = subprocess.Popen(cmd, cwd=BACKEND_DIR, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        text=True, encoding="utf-8", errors="replace", bufsize=1)
            for line in job.proc.stdout:
                job.log(line)
            job.returncode = job.proc.wait()
            if job.cancelled:
                job.state = "cancelled"
                job.log("Cancelled.")
                return
            if job.returncode != 0:
                job.state = "failed"
                job.log(f"Exited with code {job.returncode}.")
                return
        job.state = "done"
    except Exception as exc:  # noqa: BLE001 - report anything to the panel instead of dying silently
        job.state = "failed"
        job.log(f"Could not run the job: {exc}")
    finally:
        job.ended = time.time()


def _running() -> Job | None:
    return next((j for j in JOBS.values() if j.state == "running"), None)


# ----------------------------------------------------------------------------- config + status
def _load_cfg() -> dict:
    try:
        return json.loads(PANEL_CFG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _parquet_rows(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        import pyarrow.parquet as pq

        return pq.ParquetFile(path).metadata.num_rows
    except Exception:  # noqa: BLE001
        return -1


def _offline_count() -> int:
    html = ROOT_DIR / "index.html"
    if not html.exists():
        return 0
    text = html.read_text(encoding="utf-8")
    m = re.search(r'id="offline-results">(.*?)</script>', text, re.S)
    try:
        return len(json.loads(m.group(1))) if m else 0
    except ValueError:
        return 0


# ----------------------------------------------------------------------------- routes
class JobRequest(BaseModel):
    action: str
    params: dict = {}


class PanelConfig(BaseModel):
    project: str


@app.get("/", include_in_schema=False)
@app.get("/panel.html", include_in_schema=False)
def panel_page():
    return FileResponse(ROOT_DIR / "panel.html", media_type="text/html")


@app.get("/index.html", include_in_schema=False)
@app.get("/app", include_in_schema=False)
def atlas_page():
    return FileResponse(ROOT_DIR / "index.html", media_type="text/html")


@app.get("/panel/status")
def panel_status():
    exports = sorted(EXPORTS_DIR.glob("*.csv")) if EXPORTS_DIR.exists() else []
    run = _running()
    return {
        "project": _load_cfg().get("project", ""),
        "grid_cells": _parquet_rows(DATA_DIR / "grid.parquet"),
        "earth_cells": _parquet_rows(DATA_DIR / "earth_features.parquet"),
        "export_csvs": len(exports),
        "export_names": [p.name for p in exports][:60],
        "offline_entries": _offline_count(),
        "offline_expected": len(targets()) * len(features_config()["profiles"]),
        "income_groups": (DATA_DIR / "income_groups.csv").exists(),
        "running": run.summary() if run else None,
        "targets": [{"id": t["id"], "name": t["name"], "planet": t["planet"]} for t in targets()],
        "profiles": {k: v.get("label", k) for k, v in features_config()["profiles"].items()},
    }


@app.post("/panel/config")
def panel_config(cfg: PanelConfig):
    project = cfg.project.strip()
    if not PROJECT_RE.match(project):
        raise HTTPException(422, "That does not look like a Google Cloud project ID (lowercase letters, digits, hyphens).")
    PANEL_CFG.write_text(json.dumps({**_load_cfg(), "project": project}, indent=1), encoding="utf-8")
    return {"project": project}


@app.post("/jobs")
def start_job(req: JobRequest):
    label, commands = _plan(req.action, req.params or {})
    with _runner_lock:
        if _running():
            raise HTTPException(409, "Another job is still running. Wait for it or cancel it first.")
        job = Job(req.action, label, commands)
        JOBS[job.id] = job
        ORDER.append(job.id)
        threading.Thread(target=_run, args=(job,), daemon=True).start()
    return job.summary()


@app.get("/jobs")
def list_jobs():
    return [JOBS[i].summary() for i in reversed(ORDER)]


@app.get("/jobs/{job_id}")
def job_log(job_id: str, since: int = 0):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "unknown job")
    with job.lock:
        lines = job.lines[since:]
    return {**job.summary(), "since": since, "next": since + len(lines), "log": lines}


@app.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "unknown job")
    if job.state == "running" and job.proc and job.proc.poll() is None:
        job.cancelled = True
        job.proc.terminate()
    return job.summary()


@app.post("/exports/upload")
async def upload_export(request: Request, name: str):
    base = Path(name).name
    if not CSV_NAME_RE.match(base):
        raise HTTPException(422, "Only .csv files with plain names can be uploaded.")
    body = await request.body()
    if not body:
        raise HTTPException(422, "The file is empty.")
    if len(body) > 200 * 1024 * 1024:
        raise HTTPException(413, "File larger than 200 MB.")
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (EXPORTS_DIR / base).write_bytes(body)
    return {"saved": base, "bytes": len(body), "total_csvs": len(list(EXPORTS_DIR.glob("*.csv")))}
