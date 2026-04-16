from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
BOARD_DATA_DIR = DATA_DIR / "board"
BOARD_PLAYERS_FILE = BOARD_DATA_DIR / "players_2526.json"
BOARD_PLAYERS_POOL_CSV = BOARD_DATA_DIR / "players_pool.csv"
BOARD_SEASON_LABEL = "2025-26"
PLAYER_PHOTO_CACHE_DIR = PROJECT_ROOT / "static" / "player_photos"

APP_HOST = "127.0.0.1"
APP_PORT = 5000
