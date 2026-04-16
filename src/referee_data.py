from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from src.config import BOARD_DATA_DIR, PROJECT_ROOT

BOARD_REFEREES_JSON = BOARD_DATA_DIR / "referees.json"
_REFEREE_BOOTSTRAP = PROJECT_ROOT / "src" / "referees_bootstrap.json"


def referee_slug(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (name or "").strip().lower()).strip("-")
    return s or "unknown"


def referee_id(name: str) -> str:
    return f"ref-{referee_slug(name)}"


def load_referee_bundle() -> dict[str, Any]:
    if BOARD_REFEREES_JSON.is_file():
        try:
            return json.loads(BOARD_REFEREES_JSON.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    if _REFEREE_BOOTSTRAP.is_file():
        return json.loads(_REFEREE_BOOTSTRAP.read_text(encoding="utf-8"))
    return {"referees": [], "meta": {"error": "no_referee_file"}}


def list_referees() -> list[dict[str, Any]]:
    refs = load_referee_bundle().get("referees", [])
    return sorted(refs, key=lambda r: str(r.get("name", "")).lower())


def referee_by_id(rid: str) -> dict[str, Any] | None:
    rid = str(rid or "").strip()
    for r in list_referees():
        if str(r.get("id", "")) == rid:
            return r
    return None


def referee_public_dict(r: dict[str, Any]) -> dict[str, Any]:
    """Subset safe for JSON to browser."""
    return {
        "id": r.get("id"),
        "name": r.get("name"),
        "matches": int(r.get("matches", 0) or 0),
        "bias_h": float(r.get("bias_h", 0) or 0),
        "bias_d": float(r.get("bias_d", 0) or 0),
        "bias_a": float(r.get("bias_a", 0) or 0),
    }
