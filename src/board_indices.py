from __future__ import annotations

import math
from typing import Any

import pandas as pd


def _pos_group(position: str) -> str:
    p = (position or "").upper()
    if "GK" in p:
        return "GK"
    if p.startswith("F") or " F" in f" {p}":
        return "FW"
    if p.startswith("D"):
        return "DF"
    return "MF"


def _safe_float(x: Any) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(x: Any) -> int:
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return 0


def enrich_player_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Add per-90 helpers, role group, and model indices (league-relative z-scores)."""
    out = df.copy()
    out["minutes"] = out["time"].map(_safe_int)
    out["games_ct"] = out["games"].map(_safe_int)
    out["pos_group"] = out["position"].map(_pos_group)
    m = out["minutes"].clip(lower=1)
    out["npxg90"] = out["npxG"].map(_safe_float) * 90.0 / m
    out["xa90"] = out["xA"].map(_safe_float) * 90.0 / m
    out["shots90"] = out["shots"].map(_safe_float) * 90.0 / m
    out["kp90"] = out["key_passes"].map(_safe_float) * 90.0 / m
    out["xgc90"] = out["xGChain"].map(_safe_float) * 90.0 / m
    out["xgb90"] = out["xGBuildup"].map(_safe_float) * 90.0 / m

    out["atk_raw"] = (
        out["npxg90"]
        + 0.55 * out["xa90"]
        + 0.035 * out["shots90"]
        + 0.012 * out["xgc90"]
    )
    # Defensive / build-up proxy (Understat is attack-leaning; this is a framework prior).
    role_df = out["pos_group"].map({"DF": 1.0, "MF": 0.72, "FW": 0.28, "GK": 0.15}).fillna(0.4)
    out["def_raw"] = (0.55 * out["xgb90"] + 0.35 * out["kp90"]) * role_df

    # Goalkeepers: no shot/xG signal — use minutes + games as experience curve + slight buildup.
    gk_mask = out["pos_group"] == "GK"
    out.loc[gk_mask, "atk_raw"] = 0.02 * out.loc[gk_mask, "xgb90"]
    out.loc[gk_mask, "def_raw"] = 0.0
    out["gk_raw"] = 0.0
    out.loc[gk_mask, "gk_raw"] = (
        2.8 * (out.loc[gk_mask, "minutes"] / 90.0).map(math.log1p)
        + 0.35 * out.loc[gk_mask, "games_ct"].map(math.sqrt)
        + 0.25 * out.loc[gk_mask, "xgb90"]
    )

    def _z(series: pd.Series) -> pd.Series:
        mu = series.mean()
        sigma = series.std()
        if sigma and not math.isnan(sigma) and sigma > 1e-9:
            return (series - mu) / sigma
        return series * 0.0

    parts: list[pd.DataFrame] = []
    for league, grp in out.groupby("league", sort=False):
        z_atk = _z(grp["atk_raw"])
        z_def = _z(grp["def_raw"])
        z_gk = _z(grp["gk_raw"])
        chunk = pd.DataFrame(
            {
                "atk_index": (50 + 14 * z_atk).clip(18, 97),
                "def_index": (50 + 14 * z_def).clip(18, 97),
                "gk_index": (50 + 14 * z_gk).clip(25, 96),
            },
            index=grp.index,
        )
        parts.append(chunk)
    zdf = pd.concat(parts).sort_index()
    out["atk_index"] = zdf["atk_index"]
    out["def_index"] = zdf["def_index"]
    out["gk_index"] = zdf["gk_index"]
    out.loc[~gk_mask, "gk_index"] = 8.0
    return out


def frame_to_pool_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Rows ready for CSV / API consumption."""
    rows: list[dict[str, Any]] = []
    for _, r in df.iterrows():
        uid = f"u5-{r['_league_key']}-{r['id']}"
        rows.append(
            {
                "id": uid,
                "understat_id": str(r["id"]),
                "name": str(r["player_name"]),
                "club": str(r["team_title"]),
                "league": str(r["league"]),
                "position": str(r["position"]),
                "pos_group": str(r["pos_group"]),
                "minutes": int(r["minutes"]),
                "games": int(r["games_ct"]),
                "atk_index": round(float(r["atk_index"]), 4),
                "def_index": round(float(r["def_index"]), 4),
                "gk_index": round(float(r["gk_index"]), 4),
                "npxg90": round(float(r["npxg90"]), 4),
                "xa90": round(float(r["xa90"]), 4),
                "xgb90": round(float(r["xgb90"]), 4),
            }
        )
    return rows
