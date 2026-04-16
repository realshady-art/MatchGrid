from __future__ import annotations

import re
from pathlib import Path
import requests

from src.player_photos import (
    _extension_from_response,
    _extension_from_url,
    safe_photo_filename,
    thesportsdb_portrait_url,
    wikipedia_portrait_url,
)

UA = "MatchBoard/1.0 (local lineup app; https://github.com/) python-requests"


def referee_portrait_url(name: str, session: requests.Session | None = None) -> str | None:
    """
    Pro-style headshot for match officials: TheSportsDB (rare hit) then Wikipedia
    queries tailored to referees.
    """
    sess = session or requests.Session()
    u = thesportsdb_portrait_url(name, club=None, session=sess)
    if u:
        return u
    queries = (
        f"{name} (referee)",
        f"{name} football referee",
        f"{name} Premier League referee",
        name,
    )
    for q in queries:
        u = wikipedia_portrait_url(q, session=sess)
        if u:
            return u
    return None


def ensure_referee_photo_file(
    referee_id: str,
    display_name: str,
    cache_dir: Path,
    session: requests.Session | None = None,
) -> Path | None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    sess = session or requests.Session()
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", referee_id)
    pro_glob = list(cache_dir.glob(f"{cleaned}_pro.*"))
    for existing in pro_glob:
        if existing.is_file() and existing.stat().st_size > 400:
            return existing

    url = referee_portrait_url(display_name, session=sess)
    if not url:
        return None

    ext = _extension_from_url(url)
    dest = cache_dir / safe_photo_filename(referee_id, "_pro", ext)
    try:
        img = sess.get(url, headers={"User-Agent": UA}, timeout=35)
        img.raise_for_status()
        ctype = (img.headers.get("Content-Type") or "").lower()
        pathish = url.lower().split("?", 1)[0]
        looks_image = pathish.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))
        if "image" not in ctype and not looks_image:
            return None
        ext2 = _extension_from_response(ctype, url)
        if ext2 != ext:
            dest = cache_dir / safe_photo_filename(referee_id, "_pro", ext2)
        dest.write_bytes(img.content)
    except requests.RequestException:
        return None
    return dest if dest.is_file() and dest.stat().st_size > 400 else None
