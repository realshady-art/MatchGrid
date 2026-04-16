#!/usr/bin/env python3
"""
Fit referee outcome biases from football-data.co.uk Premier League results (E0.csv).

Uses empirical outcome rates per referee vs league baseline, with Dirichlet-style smoothing.
Writes data/board/referees.json (create data/board if needed).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import BOARD_DATA_DIR  # noqa: E402
from src.referee_data import referee_id  # noqa: E402

DEFAULT_URL = "https://www.football-data.co.uk/mmz4281/2526/E0.csv"
HEADERS = {"User-Agent": "MatchBoard/1.0 (research; local) python-requests"}


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def fit_from_frame(df: pd.DataFrame, *, alpha: float = 6.0, scale: float = 0.32) -> list[dict]:
    """Return list of referee records with bias_h, bias_d, bias_a for softmax logits."""
    df = df.dropna(subset=["Referee", "FTR"])
    df["Referee"] = df["Referee"].astype(str).str.strip()
    df["FTR"] = df["FTR"].astype(str).str.strip().str.upper()
    n = len(df)
    if n < 50:
        raise ValueError("too_few_matches")

    gc = df["FTR"].value_counts()
    p_h = gc.get("H", 0) / n
    p_d = gc.get("D", 0) / n
    p_a = gc.get("A", 0) / n
    eps = 1e-6

    out: list[dict] = []
    for ref, g in df.groupby("Referee"):
        name = str(ref).strip()
        if not name:
            continue
        nr = len(g)
        if nr < 3:
            continue
        nh = int((g["FTR"] == "H").sum())
        nd = int((g["FTR"] == "D").sum())
        na = int((g["FTR"] == "A").sum())
        ph = (nh + alpha * p_h) / (nr + alpha)
        pd_ = (nd + alpha * p_d) / (nr + alpha)
        pa = (na + alpha * p_a) / (nr + alpha)
        bh = scale * math.log((ph + eps) / (p_h + eps))
        bd = scale * math.log((pd_ + eps) / (p_d + eps))
        ba = scale * math.log((pa + eps) / (p_a + eps))
        out.append(
            {
                "id": referee_id(name),
                "name": name,
                "matches": nr,
                "bias_h": round(_clamp(bh, -0.45, 0.45), 5),
                "bias_d": round(_clamp(bd, -0.45, 0.45), 5),
                "bias_a": round(_clamp(ba, -0.45, 0.45), 5),
            }
        )
    return sorted(out, key=lambda r: (-r["matches"], r["name"]))


def main() -> None:
    parser = argparse.ArgumentParser(description="Train referee biases from football-data E0 CSV")
    parser.add_argument("--url", default=DEFAULT_URL, help="CSV URL (default: EPL current season)")
    parser.add_argument("--from-file", type=Path, help="Read local CSV instead of downloading")
    args = parser.parse_args()

    BOARD_DATA_DIR.mkdir(parents=True, exist_ok=True)
    dest = BOARD_DATA_DIR / "referees.json"

    if args.from_file:
        text = args.from_file.read_text(encoding="utf-8", errors="replace")
    else:
        r = requests.get(args.url, headers=HEADERS, timeout=60)
        r.raise_for_status()
        text = r.content.decode("utf-8", errors="replace")

    df = pd.read_csv(StringIO(text))
    if "Referee" not in df.columns or "FTR" not in df.columns:
        raise SystemExit("CSV missing Referee or FTR column")

    refs = fit_from_frame(df)
    bundle = {
        "referees": refs,
        "meta": {
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "source": str(args.url) if not args.from_file else str(args.from_file),
            "rows": len(df),
            "method": "smoothed log-rate vs league baseline → logit offsets (demo calibration)",
        },
    }
    dest.write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(refs)} referees to {dest}")


if __name__ == "__main__":
    main()
