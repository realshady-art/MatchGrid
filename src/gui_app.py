from __future__ import annotations

import json
import mimetypes
import re
from pathlib import Path
from typing import Any

from flask import Flask, abort, jsonify, redirect, render_template, request, send_file, url_for

from src.board_data import (
    club_labels,
    clubs_by_league,
    filter_players,
    league_labels,
    load_players_bundle,
    players_by_id,
    primary_club,
)
from src.board_predict import predict_lineup_match
from src.board_preset import DEFAULT_PRESET_AWAY_CLUB, DEFAULT_PRESET_HOME_CLUB, build_full_preset
from src.config import BOARD_DATA_DIR, PLAYER_PHOTO_CACHE_DIR, REFEREE_PHOTO_CACHE_DIR
from src.player_photos import ensure_photo_file
from src.referee_data import referee_by_id, referee_public_dict, list_referees
from src.referee_photos import ensure_referee_photo_file

BOARD_PLAYER_ID_RE = re.compile(r"^u5-[A-Za-z0-9_]+-\d+$")
BOARD_REFEREE_ID_RE = re.compile(r"^ref-[a-z0-9-]+$")


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
        "all_clubs": club_labels(),
        "clubs_by_league": clubs_by_league(),
        "preset_default_home": DEFAULT_PRESET_HOME_CLUB,
        "preset_default_away": DEFAULT_PRESET_AWAY_CLUB,
        "referees_public": [referee_public_dict(r) for r in list_referees()],
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
        club = request.args.get("club", "")
        pos_group = request.args.get("pos_group", "")
        position = request.args.get("position", "")
        limit = min(500, max(1, int(request.args.get("limit", 120))))
        bundle = load_players_bundle()
        rows = filter_players(
            search=q,
            league=league,
            club=club,
            pos_group=pos_group,
            position=position,
            limit=limit,
        )
        return jsonify(
            {
                "season": bundle.get("season", ""),
                "count": len(rows),
                "items": rows,
            }
        )

    @app.get("/api/board/preset")
    def api_board_preset():
        home_c = request.args.get("home", DEFAULT_PRESET_HOME_CLUB).strip()
        away_c = request.args.get("away", DEFAULT_PRESET_AWAY_CLUB).strip()
        if not home_c or not away_c:
            return jsonify({"error": "home_and_away_club_required"}), 400
        payload = build_full_preset(home_c, away_c)
        payload["defaults"] = {
            "home": DEFAULT_PRESET_HOME_CLUB,
            "away": DEFAULT_PRESET_AWAY_CLUB,
        }
        return jsonify(payload)

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

        ref_for_model: dict[str, Any] | None = None
        ref_raw = payload.get("referee")
        if isinstance(ref_raw, dict):
            rid = str(ref_raw.get("referee_id", "")).strip()
            if rid and BOARD_REFEREE_ID_RE.match(rid):
                rrow = referee_by_id(rid)
                if rrow:
                    ref_for_model = {
                        "bias_h": float(rrow.get("bias_h", 0) or 0),
                        "bias_d": float(rrow.get("bias_d", 0) or 0),
                        "bias_a": float(rrow.get("bias_a", 0) or 0),
                    }

        result = predict_lineup_match(home, away, roster, referee=ref_for_model)
        result["warnings"] = warnings
        if ref_for_model and isinstance(ref_raw, dict):
            rid = str(ref_raw.get("referee_id", "")).strip()
            rrow = referee_by_id(rid)
            if rrow:
                result["referee_applied"] = {
                    "id": rid,
                    "name": rrow.get("name"),
                    "matches": rrow.get("matches"),
                }
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
        path = ensure_photo_file(
            player_id,
            row["name"],
            PLAYER_PHOTO_CACHE_DIR,
            club=primary_club(str(row.get("club") or "")),
        )
        if path is None:
            abort(404)
        mime, _ = mimetypes.guess_type(path.name)
        return send_file(path, mimetype=mime or "image/jpeg")

    @app.get("/api/board/referee-photo/<path:referee_id>")
    def board_referee_photo(referee_id: str):
        if not BOARD_REFEREE_ID_RE.match(referee_id):
            abort(404)
        row = referee_by_id(referee_id)
        if not row:
            abort(404)
        REFEREE_PHOTO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = ensure_referee_photo_file(
            referee_id,
            str(row.get("name", "")),
            REFEREE_PHOTO_CACHE_DIR,
        )
        if path is None:
            abort(404)
        mime, _ = mimetypes.guess_type(path.name)
        return send_file(path, mimetype=mime or "image/jpeg")

    return app
