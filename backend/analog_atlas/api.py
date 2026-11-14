"""HTTP API for the frontend.   uvicorn analog_atlas.api:app --reload --port 8000

GET  /health
GET  /targets                      Moon/Mars targets with their feature vectors
GET  /config                       feature set, profiles, priority rules (frontend can mirror them)
POST /score  {"target_id": "cerberus", "profile": "landing", "top": 20}
             or {"features": {...v2 feature dict...}, "profile": ..., "weights": {family: w}}
POST /find-analogs  same body -> {"anchors": [...16 catalog sites, pure SI...],
                                  "discoveries": [...150 km regions from the Earth grid, with reasons...]}
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import features_config, priority_config, targets
from .features import from_target
from .pipeline import EARTH_FEATURES_PATH, _plain, find_analogs, get_target, load_candidates, rank, to_records

app = FastAPI(title="Analog Atlas API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class ScoreRequest(BaseModel):
    target_id: str | None = None
    features: dict | None = None
    profile: str = "landing"
    weights: dict | None = None
    top: int = 20
    source: str = "auto"


@app.get("/health")
def health():
    return {"ok": True, "grid_loaded": EARTH_FEATURES_PATH.exists()}


@app.get("/targets")
def list_targets():
    return [{**t, "features": from_target(t)} for t in targets()]


@app.get("/config")
def config():
    return {"features": features_config(), "priority": priority_config()}


@app.post("/score")
def score_endpoint(req: ScoreRequest):
    if req.profile not in features_config()["profiles"] and not req.weights:
        raise HTTPException(400, f"unknown profile '{req.profile}'")
    if req.features:
        feats = req.features
    elif req.target_id:
        try:
            _, feats = get_target(req.target_id)
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
    else:
        raise HTTPException(400, "give target_id or features")
    try:
        cands, source = load_candidates(req.source)
    except FileNotFoundError as exc:
        raise HTTPException(409, str(exc)) from exc
    head = rank(feats, cands, profile=req.profile, custom_weights=req.weights, top=max(1, min(req.top, 500)))
    return {"source": source, "profile": req.profile, "results": to_records(head)}


@app.post("/find-analogs")
def find_endpoint(req: ScoreRequest):
    """Anchor & Discover for a preset target or a feature vector (Step C)."""
    if req.profile not in features_config()["profiles"] and not req.weights:
        raise HTTPException(400, f"unknown profile '{req.profile}'")
    if not req.target_id and not req.features:
        raise HTTPException(400, "give target_id or features")
    profile = req.profile if req.profile in features_config()["profiles"] else "science"
    try:
        result = find_analogs(req.target_id, features=req.features, profile=profile, custom_weights=req.weights,
                              top=max(1, min(req.top, 100)), source=req.source)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    return _plain(result)
