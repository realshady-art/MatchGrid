from __future__ import annotations

from pathlib import Path

import requests

from src.config import LIVE_DATA_DIR, LIVE_DATA_FILENAME, LIVE_DATA_URL, RAW_DATA_DIR
from src.utils import ensure_directories


HISTORICAL_SEASONS = [
    "1516",
    "1617",
    "1718",
    "1819",
    "1920",
    "2021",
    "2122",
    "2223",
    "2324",
    "2425",
]


def _download_file(url: str, destination: Path) -> None:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    destination.write_text(response.text, encoding="utf-8")


def bootstrap_project_data() -> list[Path]:
    ensure_directories([RAW_DATA_DIR, LIVE_DATA_DIR])
    downloaded: list[Path] = []

    for season in HISTORICAL_SEASONS:
        destination = RAW_DATA_DIR / f"{season}_E0.csv"
        if not destination.exists():
            url = f"https://www.football-data.co.uk/mmz4281/{season}/E0.csv"
            _download_file(url, destination)
            downloaded.append(destination)

    live_destination = LIVE_DATA_DIR / LIVE_DATA_FILENAME
    if not live_destination.exists():
        _download_file(LIVE_DATA_URL, live_destination)
        downloaded.append(live_destination)

    return downloaded
