from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.config import BOARD_PLAYERS_FILE, BOARD_PLAYERS_POOL_CSV


def _normalize_from_json(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(raw["id"]),
        "name": str(raw.get("name", "")),
        "club": str(raw.get("club", "")),
        "league": str(raw.get("league", "")),
        "position": str(raw.get("position", "")),
        "pos_group": str(raw.get("pos_group", _infer_pos_group(raw.get("position", "")))),
        "rating": float(raw.get("rating", 70)),
        "minutes": int(raw.get("minutes", 0)),
        "atk_index": float(raw.get("atk_index", raw.get("rating", 70))),
        "def_index": float(raw.get("def_index", raw.get("rating", 70))),
        "gk_index": float(raw.get("gk_index", 15.0)),
    }


def _infer_pos_group(position: str) -> str:
    p = (position or "").upper()
    if "GK" in p:
        return "GK"
    if p.startswith("F") or " F" in f" {p}":
        return "FW"
    if p.startswith("D"):
        return "DF"
    return "MF"


def _normalize_from_csv_row(row: pd.Series) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "name": str(row["name"]),
        "club": str(row["club"]),
        "league": str(row["league"]),
        "position": str(row["position"]),
        "pos_group": str(row.get("pos_group", _infer_pos_group(str(row["position"])))),
        "rating": float((float(row["atk_index"]) + float(row["def_index"])) / 2),
        "minutes": int(row["minutes"]),
        "atk_index": float(row["atk_index"]),
        "def_index": float(row["def_index"]),
        "gk_index": float(row["gk_index"]),
    }


def load_players_bundle(
    csv_path: Path | None = None,
    json_path: Path | None = None,
) -> dict[str, Any]:
    """
    Prefer players_pool.csv (scraped + modelled). Fallback to legacy JSON bundle.
    """
    csv_p = csv_path or BOARD_PLAYERS_POOL_CSV
    json_p = json_path or BOARD_PLAYERS_FILE

    if csv_p.is_file():
        try:
            df = pd.read_csv(csv_p)
        except Exception as exc:  # noqa: BLE001
            return {"season": "", "players": [], "error": f"csv_read_error:{exc}"}
        players = [_normalize_from_csv_row(row) for _, row in df.iterrows()]
        meta_note = f"CSV:{csv_p.name}"
        return {
            "season": "",
            "source_note": meta_note,
            "players": players,
        }

    if not json_p.is_file():
        return {"season": "", "players": [], "error": f"missing_file:{csv_p} and {json_p}"}
    try:
        data = json.loads(json_p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"season": "", "players": [], "error": f"invalid_json:{exc}"}
    players = [_normalize_from_json(x) for x in data.get("players", [])]
    return {
        "season": str(data.get("season", "")),
        "source_note": str(data.get("source_note", "")),
        "players": players,
    }


def players_by_id(csv_path: Path | None = None, json_path: Path | None = None) -> dict[str, dict[str, Any]]:
    bundle = load_players_bundle(csv_path=csv_path, json_path=json_path)
    return {p["id"]: p for p in bundle["players"]}


def filter_players(
    *,
    search: str = "",
    league: str = "",
    limit: int = 80,
    csv_path: Path | None = None,
    json_path: Path | None = None,
) -> list[dict[str, Any]]:
    bundle = load_players_bundle(csv_path=csv_path, json_path=json_path)
    rows = list(bundle["players"])
    q = search.strip().lower()
    if q:
        rows = [
            p
            for p in rows
            if q in p["name"].lower() or q in p["club"].lower() or q in p["id"].lower()
        ]
    lg = league.strip()
    if lg:
        rows = [p for p in rows if p["league"] == lg]
    return rows[: max(1, min(limit, 500))]


def league_labels(csv_path: Path | None = None, json_path: Path | None = None) -> list[str]:
    bundle = load_players_bundle(csv_path=csv_path, json_path=json_path)
    seen: set[str] = set()
    out: list[str] = []
    for p in bundle["players"]:
        L = p["league"]
        if L and L not in seen:
            seen.add(L)
            out.append(L)
    return sorted(out)
