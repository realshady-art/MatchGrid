from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.config import CACHE_DIR
from src.utils import ensure_directories


class CacheManager:
    def __init__(self, cache_dir: Path = CACHE_DIR) -> None:
        self.cache_dir = cache_dir
        ensure_directories(
            [
                self.cache_dir,
                self.cache_dir / "team_form",
                self.cache_dir / "head_to_head",
            ]
        )

    def load(self, category: str, key: str, ttl_hours: int) -> dict[str, Any] | None:
        path = self._path_for(category, key)
        if not path.exists():
            return None

        payload = json.loads(path.read_text(encoding="utf-8"))
        fetched_at = datetime.fromisoformat(payload["fetched_at"])
        if datetime.now(timezone.utc) - fetched_at > timedelta(hours=ttl_hours):
            return None
        return payload["data"]

    def store(self, category: str, key: str, data: dict[str, Any]) -> None:
        path = self._path_for(category, key)
        payload = {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _path_for(self, category: str, key: str) -> Path:
        safe_key = key.lower().replace(" ", "_").replace("/", "_")
        return self.cache_dir / category / f"{safe_key}.json"
