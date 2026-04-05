from pathlib import Path

import pandas as pd

from src.config import DATE_COLUMN, HOME_TEAM_COLUMN, AWAY_TEAM_COLUMN, RAW_DATA_DIR, SEASON_COLUMN, TARGET_COLUMN


COLUMN_MAP = {
    "Date": DATE_COLUMN,
    "HomeTeam": HOME_TEAM_COLUMN,
    "AwayTeam": AWAY_TEAM_COLUMN,
    "FTHG": "home_goals",
    "FTAG": "away_goals",
    "FTR": TARGET_COLUMN,
}


def infer_season_from_filename(path: Path) -> str:
    stem = path.stem.lower().replace("_", "").replace("-", "")
    digits = "".join(char for char in stem if char.isdigit())
    if len(digits) >= 4:
        start = int(digits[:2])
        end = int(digits[2:4])
        start_year = 2000 + start
        end_year = 2000 + end
        return f"{start_year}-{end_year}"
    return path.stem


def load_season_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = [col for col in COLUMN_MAP if col not in frame.columns]
    if missing:
        raise ValueError(f"{path.name} is missing required columns: {missing}")

    frame = frame[list(COLUMN_MAP)].rename(columns=COLUMN_MAP).copy()
    frame[DATE_COLUMN] = pd.to_datetime(frame[DATE_COLUMN], format="%d/%m/%Y", errors="coerce")
    frame = frame.dropna(subset=[DATE_COLUMN, HOME_TEAM_COLUMN, AWAY_TEAM_COLUMN, TARGET_COLUMN])
    frame[SEASON_COLUMN] = infer_season_from_filename(path)
    frame[TARGET_COLUMN] = frame[TARGET_COLUMN].str.upper().str.strip()
    return frame


def load_all_raw_data(raw_dir: Path = RAW_DATA_DIR) -> pd.DataFrame:
    csv_paths = sorted(raw_dir.glob("*.csv"))
    if not csv_paths:
        raise FileNotFoundError(
            f"No CSV files found in {raw_dir}. Add EPL season files before running the pipeline."
        )

    frames = [load_season_csv(path) for path in csv_paths]
    matches = pd.concat(frames, ignore_index=True)
    matches = matches.sort_values(DATE_COLUMN).reset_index(drop=True)
    return matches
