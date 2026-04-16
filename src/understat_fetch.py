from __future__ import annotations

import time
from typing import Any

import requests

UNDERSTAT_AJAX_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MatchBoard/1.0; +local research)",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json,*/*",
}

# Keys must match Understat URLs (see understat.com league dropdown)
UNDERSTAT_LEAGUES: dict[str, str] = {
    "EPL": "Premier League",
    "La_liga": "La Liga",
    "Bundesliga": "Bundesliga",
    "Serie_A": "Serie A",
    "Ligue_1": "Ligue 1",
}

DEFAULT_SEASON = "2025"  # site: 2025/2026


def fetch_league_data(league_key: str, season: str = DEFAULT_SEASON, *, pause_s: float = 1.0) -> dict[str, Any]:
    """
    Pull league bundle (teams, players, dates) from Understat via public GET endpoint.
    Respectful: single-threaded, default pause between leagues.
    """
    if league_key not in UNDERSTAT_LEAGUES:
        raise ValueError(f"Unknown league key {league_key!r}; expected one of {sorted(UNDERSTAT_LEAGUES)}")
    url = f"https://understat.com/getLeagueData/{league_key}/{season}"
    session = requests.Session()
    response = session.get(url, headers=UNDERSTAT_AJAX_HEADERS, timeout=60)
    response.raise_for_status()
    if pause_s:
        time.sleep(pause_s)
    return response.json()


def fetch_all_big_five(season: str = DEFAULT_SEASON, *, pause_s: float = 1.2) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, league_label in UNDERSTAT_LEAGUES.items():
        payload = fetch_league_data(key, season, pause_s=pause_s)
        players = payload.get("players") or []
        for p in players:
            rows.append(
                {
                    **p,
                    "_league_key": key,
                    "league": league_label,
                }
            )
    return rows
