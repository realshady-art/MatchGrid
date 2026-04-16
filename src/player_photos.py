from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

# https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy
WIKI_HEADERS = {
    "User-Agent": "MatchBoard/1.0 (educational local app; https://github.com/) python-requests",
    "Accept": "application/json",
}

_THUMB_SIZE = 800
_WIKI_API = "https://en.wikipedia.org/w/api.php"


def wikipedia_portrait_url(player_name: str, session: requests.Session | None = None) -> str | None:
    """Resolve a high-res Wikipedia thumbnail for a person name (best-effort)."""
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


def safe_photo_filename(player_id: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", player_id)
    return f"{cleaned}.jpg"


def ensure_photo_file(
    player_id: str,
    player_name: str,
    cache_dir: Path,
    session: requests.Session | None = None,
) -> Path | None:
    """
    Download portrait into cache_dir if missing. Returns path to JPEG or None.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    dest = cache_dir / safe_photo_filename(player_id)
    if dest.is_file() and dest.stat().st_size > 500:
        return dest
    url = wikipedia_portrait_url(player_name, session=session)
    if not url:
        return None
    sess = session or requests.Session()
    try:
        img = sess.get(url, headers={"User-Agent": WIKI_HEADERS["User-Agent"]}, timeout=35)
        img.raise_for_status()
        if "image" not in img.headers.get("Content-Type", "") and not url.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            return None
        dest.write_bytes(img.content)
    except requests.RequestException:
        return None
    return dest if dest.is_file() and dest.stat().st_size > 500 else None


def photo_url_for_player(player_id: str) -> str:
    """URL path served by Flask (see gui_app)."""
    return f"/api/board/player-photo/{quote(player_id, safe='')}"
