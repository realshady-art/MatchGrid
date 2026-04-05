from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Flask, abort, jsonify, redirect, render_template, request, url_for

from src.bootstrap_data import bootstrap_project_data
from src.config import DATABASE_PATH, OUTPUT_MODELS_DIR
from src.live_data_provider import FootballDataCsvProvider, LiveDataProviderError
from src.predict_service import predict_match
from src.storage import (
    create_prediction_record,
    get_prediction_record,
    init_db,
    list_prediction_records,
)


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).resolve().parent.parent / "templates"),
        static_folder=str(Path(__file__).resolve().parent.parent / "static"),
    )

    bootstrap_project_data()
    init_db(DATABASE_PATH)

    @app.get("/")
    def index() -> str:
        provider = FootballDataCsvProvider()
        teams = provider.available_teams()
        recent_predictions = list_prediction_records(limit=8)
        latest_result = recent_predictions[0] if recent_predictions else None
        model_ready = (OUTPUT_MODELS_DIR / "logistic_regression.joblib").exists()
        return render_template(
            "index.html",
            teams=teams,
            recent_predictions=recent_predictions,
            latest_result=latest_result,
            model_ready=model_ready,
            error=None,
        )

    @app.post("/predict")
    def predict_view():
        home_team = request.form.get("home_team", "").strip()
        away_team = request.form.get("away_team", "").strip()
        provider = FootballDataCsvProvider()
        teams = provider.available_teams()
        recent_predictions = list_prediction_records(limit=8)
        model_ready = (OUTPUT_MODELS_DIR / "logistic_regression.joblib").exists()

        if not home_team or not away_team:
            return render_template(
                "index.html",
                teams=teams,
                recent_predictions=recent_predictions,
                latest_result=recent_predictions[0] if recent_predictions else None,
                model_ready=model_ready,
                error="Enter both team names before requesting a prediction.",
            )

        try:
            result = predict_match(home_team=home_team, away_team=away_team, provider=provider)
        except FileNotFoundError:
            return render_template(
                "index.html",
                teams=teams,
                recent_predictions=recent_predictions,
                latest_result=recent_predictions[0] if recent_predictions else None,
                model_ready=False,
                error="No trained model found. Run the training pipeline first.",
            )
        except LiveDataProviderError as exc:
            return render_template(
                "index.html",
                teams=teams,
                recent_predictions=recent_predictions,
                latest_result=recent_predictions[0] if recent_predictions else None,
                model_ready=model_ready,
                error=str(exc),
            )

        record_id = create_prediction_record(
            created_at=datetime.now(timezone.utc).isoformat(),
            home_team=result["home_team"],
            away_team=result["away_team"],
            fixture_utc_date=result["fixture_utc_date"],
            prediction=result["prediction"],
            probabilities=result.get("probabilities"),
            features=result["features_used"],
            summary=result["data_summary"],
        )
        return redirect(url_for("prediction_detail", record_id=record_id))

    @app.get("/history")
    def history() -> str:
        return render_template("history.html", records=list_prediction_records(limit=100))

    @app.get("/predictions/<int:record_id>")
    def prediction_detail(record_id: int) -> str:
        record = get_prediction_record(record_id)
        if record is None:
            abort(404)
        return render_template("detail.html", record=record)

    @app.get("/api/timeline")
    def timeline_api():
        records = list_prediction_records(limit=12)
        return jsonify(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "items": records,
            }
        )

    return app
