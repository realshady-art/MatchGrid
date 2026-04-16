from __future__ import annotations

from typing import Any, Literal

from src.board_data import club_tokens, load_players_bundle

# Default opening matchup when the page loads
DEFAULT_PRESET_HOME_CLUB = "Manchester United"
DEFAULT_PRESET_AWAY_CLUB = "Manchester City"

# Rough 4-3-3-style slots: home attacks right (higher x). Away uses mirrored x.
_SLOT_HOME: list[tuple[float, float]] = [
    (0.08, 0.5),  # GK
    (0.20, 0.10),
    (0.20, 0.34),
    (0.20, 0.66),
    (0.20, 0.90),  # back four
    (0.37, 0.22),
    (0.37, 0.50),
    (0.37, 0.78),  # midfield three
    (0.54, 0.28),
    (0.54, 0.50),
    (0.54, 0.72),  # front three
]


def _eligible_for_club(club: str, players: list[dict[str, Any]]) -> list[dict[str, Any]]:
    c = (club or "").strip()
    if not c:
        return []
    return [p for p in players if c in club_tokens(str(p.get("club", "")))]


def _pick_eleven(players: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Prefer one goalkeeper, then fill by minutes (real-season usage proxy)."""
    if not players:
        return []
    el = sorted(players, key=lambda p: -int(p.get("minutes", 0) or 0))
    chosen: list[dict[str, Any]] = []
    seen: set[str] = set()
    for p in el:
        if str(p.get("pos_group", "")) == "GK" and p["id"] not in seen:
            chosen.append(p)
            seen.add(p["id"])
            break
    for p in el:
        if len(chosen) >= 11:
            break
        if p["id"] not in seen:
            chosen.append(p)
            seen.add(p["id"])
    order_rank = {"GK": 0, "DF": 1, "MF": 2, "FW": 3}
    chosen.sort(
        key=lambda p: (
            order_rank.get(str(p.get("pos_group", "")), 5),
            -int(p.get("minutes", 0) or 0),
        )
    )
    return chosen[:11]


def build_side_preset(
    club: str,
    side: Literal["home", "away"],
) -> list[dict[str, Any]]:
    """
    Return [{ "player": roster dict, "x": float, "y": float }, ...] for up to 11 players.
    """
    bundle = load_players_bundle()
    players: list[dict[str, Any]] = list(bundle.get("players", []))
    el = _eligible_for_club(club, players)
    eleven = _pick_eleven(el)
    out: list[dict[str, Any]] = []
    for i, p in enumerate(eleven):
        if i >= len(_SLOT_HOME):
            break
        x0, y0 = _SLOT_HOME[i]
        x = float(x0) if side == "home" else float(1.0 - x0)
        out.append({"player": p, "x": x, "y": float(y0)})
    return out


def build_full_preset(home_club: str, away_club: str) -> dict[str, Any]:
    return {
        "home": build_side_preset(home_club, "home"),
        "away": build_side_preset(away_club, "away"),
        "home_club": (home_club or "").strip(),
        "away_club": (away_club or "").strip(),
    }
