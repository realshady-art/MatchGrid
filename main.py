import argparse
import os
import subprocess
import sys
from pathlib import Path

from src.config import APP_HOST, APP_PORT
from src.gui_app import create_app


def run_fetch_board_data() -> None:
    root = Path(__file__).resolve().parent
    script = root / "scripts" / "build_players_pool.py"
    env = {**os.environ, "PYTHONPATH": str(root)}
    subprocess.check_call([sys.executable, str(script)], env=env, cwd=str(root))


def run_gui(host: str, port: int) -> None:
    app = create_app()
    app.run(host=host, port=port, debug=False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Match Board — lineup prediction UI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "fetch-board-data",
        help="Download Big-5 player stats (Understat) into data/board/players_pool.csv",
    )
    gui_parser = subparsers.add_parser("gui", help="Run the Match Board web app")
    gui_parser.add_argument("--host", default=APP_HOST, help="Bind host")
    gui_parser.add_argument("--port", default=APP_PORT, type=int, help="Bind port")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "fetch-board-data":
        run_fetch_board_data()
    elif args.command == "gui":
        run_gui(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
