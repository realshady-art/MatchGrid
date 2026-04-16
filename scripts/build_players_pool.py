#!/usr/bin/env python3
"""Fetch Big-5 player season data (Understat public endpoints) and write players_pool.csv."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.board_indices import enrich_player_frame, frame_to_pool_records
from src.config import BOARD_DATA_DIR, BOARD_PLAYERS_FILE, BOARD_SEASON_LABEL
from src.understat_fetch import DEFAULT_SEASON, fetch_all_big_five

POOL_CSV = BOARD_DATA_DIR / "players_pool.csv"
META_JSON = BOARD_DATA_DIR / "players_pool.meta.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build offline players_pool.csv from Understat")
    parser.add_argument("--season", default=DEFAULT_SEASON, help="Understat season year, e.g. 2025 for 2025/26")
    parser.add_argument("--pause", type=float, default=1.2, help="Seconds between league requests")
    parser.add_argument("--from-json", type=Path, help="Skip network; load raw JSON list from file")
    args = parser.parse_args()

    BOARD_DATA_DIR.mkdir(parents=True, exist_ok=True)

    if args.from_json:
        raw = json.loads(args.from_json.read_text(encoding="utf-8"))
    else:
        raw = fetch_all_big_five(season=args.season, pause_s=args.pause)

    df = pd.DataFrame(raw)
    if df.empty:
        raise SystemExit("No player rows fetched.")
    df = enrich_player_frame(df)
    records = frame_to_pool_records(df)
    out_df = pd.DataFrame(records)
    out_df.to_csv(POOL_CSV, index=False)

    meta = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "season_label": BOARD_SEASON_LABEL,
        "understat_season": args.season,
        "source": "understat.com/getLeagueData (scraped, no third-party sports API)",
        "row_count": len(records),
        "csv_path": "data/board/players_pool.csv",
    }
    META_JSON.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    # Keep JSON bundle in sync for any legacy readers
    bundle = {
        "season": BOARD_SEASON_LABEL,
        "source_note": meta["source"],
        "players": [
            {
                "id": r["id"],
                "name": r["name"],
                "club": r["club"],
                "league": r["league"],
                "position": r["position"],
                "pos_group": r["pos_group"],
                "rating": round((r["atk_index"] + r["def_index"]) / 2, 2),
                "minutes": r["minutes"],
                "atk_index": r["atk_index"],
                "def_index": r["def_index"],
                "gk_index": r["gk_index"],
            }
            for r in records
        ],
    }
    BOARD_PLAYERS_FILE.write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Wrote {len(records)} players to {POOL_CSV}")
    print(f"Meta: {META_JSON}")


if __name__ == "__main__":
    main()
