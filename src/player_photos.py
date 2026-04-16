from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

# Wikimedia — only used if TheSportsDB has no match (rare); many articles still use casual shots.
WIKI_HEADERS = {
    "User-Agent": "MatchBoard/1.0 (local lineup app; https://github.com/) python-requests",
    "Accept": "application/json",
}

_THUMB_SIZE = 800
_WIKI_API = "https://en.wikipedia.org/w/api.php"

# TheSportsDB API key — default is public dev key; override with env for your own quota.
TSDB_API_KEY = os.environ.get("THESPORTSDB_API_KEY", "3")
_TSDB_SEARCH = "https://www.thesportsdb.com/api/v1/json/{key}/searchplayers.php"
_TSDB_HEADERS = {
    "User-Agent": WIKI_HEADERS["User-Agent"],
    "Accept": "application/json",
}

_TEAM_STOP = frozenset(
    {"fc", "cf", "sc", "afc", "the", "club", "de", "ac", "sv", "fk", "if", "bk"}
)


def _pick_tsdb_image_url(player: dict[str, Any]) -> str | None:
    """Prefer cutout (pro-style on transparent / uniform bg), then thumb, then 3D render."""
    for key in ("strCutout", "strThumb", "strRender"):
        u = player.get(key)
        if isinstance(u, str) and u.startswith("http"):
            return u.strip()
    return None


def _team_match_score(club: str, str_team: str) -> int:
    if not club or not str_team:
        return 0
    a = club.strip().lower()
    b = str_team.strip().lower()
    if a == b:
        return 200
    if a in b or b in a:
        return 120
    ta = {w for w in re.findall(r"[a-z0-9]+", a) if w not in _TEAM_STOP and len(w) > 1}
    tb = {w for w in re.findall(r"[a-z0-9]+", b) if w not in _TEAM_STOP and len(w) > 1}
    return len(ta & tb) * 25


def thesportsdb_portrait_url(
    player_name: str,
    club: str | None = None,
    session: requests.Session | None = None,
) -> str | None:
    """Best-effort pro-style portrait from TheSportsDB (cutout / thumb)."""
    name = (player_name or "").strip()
    if len(name) < 2:
        return None
    q = re.sub(r"\s+", "_", name)
    sess = session or requests.Session()
    url = _TSDB_SEARCH.format(key=TSDB_API_KEY) + f"?p={quote(q)}"
    try:
        r = sess.get(url, headers=_TSDB_HEADERS, timeout=25)
        r.raise_for_status()
        payload: dict[str, Any] = r.json()
    except (requests.RequestException, ValueError):
        return None

    raw = payload.get("player")
    if raw is None:
        return None
    players: list[dict[str, Any]]
    if isinstance(raw, dict):
        players = [raw]
    elif isinstance(raw, list):
        players = [p for p in raw if isinstance(p, dict)]
    else:
        return None
    if not players:
        return None

    club_hint = (club or "").strip()
    best_url: str | None = None
    best_score = -1
    for pl in players:
        img = _pick_tsdb_image_url(pl)
        if not img:
            continue
        str_team = str(pl.get("strTeam") or "")
        sc = _team_match_score(club_hint, str_team)
        if not club_hint:
            sc = 0
        if sc > best_score:
            best_score = sc
            best_url = img

    if best_url:
        return best_url

    # No club hint or no team overlap: first row with any image
    for pl in players:
        img = _pick_tsdb_image_url(pl)
        if img:
            return img
    return None


def wikipedia_portrait_url(player_name: str, session: requests.Session | None = None) -> str | None:
    """Fallback thumbnail from Wikipedia search (quality varies)."""
    sess = session or requests.Session()
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": player_name,
        "gsrnamespace": 0,
        "gsrlimit": 1,
        "prop": "pageimages",
        "piprop": "thumbnail",
        "pithumbsize": _THUMB_SIZE,
        "format": "json",
    }
    try:
        r = sess.get(_WIKI_API, params=params, headers=WIKI_HEADERS, timeout=25)
        r.raise_for_status()
        payload: dict[str, Any] = r.json()
    except (requests.RequestException, ValueError):
        return None
    pages = (payload.get("query") or {}).get("pages") or {}
    for _pid, page in pages.items():
        thumb = page.get("thumbnail") or {}
        src = thumb.get("source")
        if isinstance(src, str) and src.startswith("http"):
            return src
    return None


def safe_photo_filename(player_id: str, suffix: str, ext: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", player_id)
    ext = ext if ext.startswith(".") else f".{ext}"
    return f"{cleaned}{suffix}{ext}"


def _extension_from_url(url: str) -> str:
    lower = url.split("?", 1)[0].lower()
    if lower.endswith(".png"):
        return ".png"
    if lower.endswith(".webp"):
        return ".webp"
    if lower.endswith(".gif"):
        return ".gif"
    return ".jpg"


def _extension_from_response(content_type: str, url: str) -> str:
    ct = (content_type or "").split(";")[0].strip().lower()
    if "png" in ct:
        return ".png"
    if "webp" in ct:
        return ".webp"
    if "gif" in ct:
        return ".gif"
    return _extension_from_url(url)


def ensure_photo_file(
    player_id: str,
    player_name: str,
    cache_dir: Path,
    club: str | None = None,
    session: requests.Session | None = None,
) -> Path | None:
    """
    Download a pro-style portrait (TheSportsDB cutout/thumb first) into cache_dir.
    Uses filenames like ``{id}_pro.png`` so older Wikipedia-only caches are ignored.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    sess = session or requests.Session()

    # Reuse any existing pro cache (any image ext we may have written before)
    pro_glob = list(cache_dir.glob(f"{re.sub(r'[^a-zA-Z0-9._-]+', '_', player_id)}_pro.*"))
    for existing in pro_glob:
        if existing.is_file() and existing.stat().st_size > 400:
            return existing

    url = thesportsdb_portrait_url(player_name, club=club, session=sess)
    if not url:
        url = wikipedia_portrait_url(player_name, session=sess)
    if not url:
        return None

    ext = _extension_from_url(url)
    dest = cache_dir / safe_photo_filename(player_id, "_pro", ext)
    try:
        img = sess.get(url, headers={"User-Agent": _TSDB_HEADERS["User-Agent"]}, timeout=35)
        img.raise_for_status()
        ctype = (img.headers.get("Content-Type") or "").lower()
        pathish = url.lower().split("?", 1)[0]
        looks_image = pathish.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))
        if "image" not in ctype and not looks_image:
            return None
        ext2 = _extension_from_response(ctype, url)
        if ext2 != ext:
            dest = cache_dir / safe_photo_filename(player_id, "_pro", ext2)
        dest.write_bytes(img.content)
    except requests.RequestException:
        return None
    return dest if dest.is_file() and dest.stat().st_size > 400 else None


def photo_url_for_player(player_id: str) -> str:
    """URL path served by Flask (see gui_app)."""
    return f"/api/board/player-photo/{quote(player_id, safe='')}"
