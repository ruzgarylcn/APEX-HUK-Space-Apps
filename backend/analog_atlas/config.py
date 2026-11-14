"""Paths and config loading. All tunables live in backend/config/*.json."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "out"


def _load(name: str) -> dict:
    with open(CONFIG_DIR / name, encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=None)
def features_config() -> dict:
    return _load("features.json")


@lru_cache(maxsize=None)
def priority_config() -> dict:
    return _load("priority.json")


@lru_cache(maxsize=None)
def targets() -> list[dict]:
    return _load("targets.json")


def numeric_features() -> list[dict]:
    return [f for f in features_config()["features"] if not f.get("categorical")]


def numeric_keys() -> list[str]:
    return [f["key"] for f in numeric_features()]


def family_ids() -> list[str]:
    return [f["id"] for f in features_config()["families"]]
