from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from flask import Flask, abort, jsonify, redirect, render_template, request, send_file, url_for

from src.board_data import filter_players, league_labels, load_players_bundle, players_by_id
from src.board_predict import predict_lineup_match
from src.config import BOARD_DATA_DIR, PLAYER_PHOTO_CACHE_DIR
from src.player_photos import ensure_photo_file

BOARD_PLAYER_ID_RE = re.compile(r"^u5-[A-Za-z0-9_]+-\d+$")


def _board_template_context() -> dict[str, Any]:
    bundle = load_players_bundle()
    players = bundle.get("players", [])
    board_ready = len(players) > 0
    meta_path = BOARD_DATA_DIR / "players_pool.meta.json"
    scrape_meta: dict[str, Any] = {}
    if meta_path.is_file():
        try:
            scrape_meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            scrape_meta = {}
    board_season = bundle.get("season") or scrape_meta.get("season_label") or ""
    if scrape_meta.get("understat_season"):
        board_season = f"{board_season} (Understat {scrape_meta['understat_season']})".strip()
    return {
        "board_ready": board_ready,
        "board_season": board_season,
        "board_error": bundle.get("error"),
        "leagues": league_labels(),
        "roster_count": len(players),
    }


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).resolve().parent.parent / "templates"),
        static_folder=str(Path(__file__).resolve().parent.parent / "static"),
    )

    @app.get("/")
    def index():
        return render_template("match_board.html", **_board_template_context())

    @app.get("/board")
    def board_alias():
        return redirect(url_for("index"))

    @app.get("/api/board/players")
    def api_board_players():
        q = request.args.get("q", "")
        league = request.args.get("league", "")
        limit = min(500, max(1, int(request.args.get("limit", 120))))
        bundle = load_players_bundle()
        rows = filter_players(search=q, league=league, limit=limit)
        return jsonify(
            {
                "season": bundle.get("season", ""),
                "count": len(rows),
                "items": rows,
            }
        )

    @app.post("/api/board/predict")
    def api_board_predict():
        payload = request.get_json(force=True, silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "expected_json_object"}), 400
        raw_home = payload.get("home")
        raw_away = payload.get("away")
        if not isinstance(raw_home, list) or not isinstance(raw_away, list):
            return jsonify({"error": "home_and_away_must_be_arrays"}), 400

        def _normalize_side(items: list[Any]) -> tuple[list[dict[str, Any]], list[str]]:
            out: list[dict[str, Any]] = []
            warnings: list[str] = []
            for i, row in enumerate(items):
                if not isinstance(row, dict):
                    warnings.append(f"ignored_non_object:{i}")
                    continue
                pid = str(row.get("player_id", "")).strip()
                if not pid:
                    warnings.append(f"missing_player_id:{i}")
                    continue
                try:
                    x = float(row.get("x", 0.5))
                    y = float(row.get("y", 0.5))
                except (TypeError, ValueError):
                    warnings.append(f"bad_coords:{i}")
                    continue
                out.append({"player_id": pid, "x": x, "y": y})
            return out, warnings

        home, w1 = _normalize_side(raw_home)
        away, w2 = _normalize_side(raw_away)
        warnings = w1 + w2
        roster = players_by_id()
        result = predict_lineup_match(home, away, roster)
        result["warnings"] = warnings
        return jsonify(result)

    @app.get("/api/board/player-photo/<path:player_id>")
    def board_player_photo(player_id: str):
        if not BOARD_PLAYER_ID_RE.match(player_id):
            abort(404)
        roster = players_by_id()
        row = roster.get(player_id)
        if not row:
            abort(404)
        PLAYER_PHOTO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = ensure_photo_file(player_id, row["name"], PLAYER_PHOTO_CACHE_DIR)
        if path is None:
            abort(404)
        return send_file(path, mimetype="image/jpeg")

    return app
