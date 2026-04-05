from pathlib import Path
import os


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
LIVE_DATA_DIR = DATA_DIR / "live"
INTERIM_DATA_DIR = DATA_DIR / "interim"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
CACHE_DIR = PROJECT_ROOT / "cache"

OUTPUT_DIR = PROJECT_ROOT / "outputs"
OUTPUT_MODELS_DIR = OUTPUT_DIR / "models"
OUTPUT_TABLES_DIR = OUTPUT_DIR / "tables"
OUTPUT_FIGURES_DIR = OUTPUT_DIR / "figures"

TARGET_COLUMN = "result"
DATE_COLUMN = "date"
HOME_TEAM_COLUMN = "home_team"
AWAY_TEAM_COLUMN = "away_team"
SEASON_COLUMN = "season"

TRAIN_SEASONS = [
    "2015-2016",
    "2016-2017",
    "2017-2018",
    "2018-2019",
    "2019-2020",
    "2020-2021",
    "2021-2022",
    "2022-2023",
]
VALIDATION_SEASONS = ["2023-2024"]
TEST_SEASONS = ["2024-2025"]

ROLLING_WINDOWS = (3, 5)

MODEL_RANDOM_STATE = 42
TARGET_SEASON = "2025-2026"
LIVE_SEASON_CODE = "2526"
LIVE_COMPETITION_CODE = "E0"
LIVE_DATA_URL = f"https://www.football-data.co.uk/mmz4281/{LIVE_SEASON_CODE}/{LIVE_COMPETITION_CODE}.csv"
LIVE_DATA_FILENAME = f"{LIVE_SEASON_CODE}_{LIVE_COMPETITION_CODE}.csv"

CACHE_TTL_HOURS = {
    "fixture": 6,
    "team_form": 6,
    "head_to_head": 24,
}
