from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from src.cache_manager import CacheManager
from src.config import CACHE_TTL_HOURS, OUTPUT_MODELS_DIR, TARGET_SEASON
from src.live_data_provider import LiveDataProvider, PlaceholderLiveDataProvider


def _model_path(model_name: str = "logistic_regression") -> Path:
    return Path(OUTPUT_MODELS_DIR) / f"{model_name}.joblib"


def _build_live_feature_row(
    home_data: dict[str, Any],
    away_data: dict[str, Any],
    h2h_data: dict[str, Any],
) -> pd.DataFrame:
    row = {
        "home_rank_before_match": 0,
        "away_rank_before_match": 0,
        "rank_diff": 0,
        "home_rest_days": home_data["rest_days"],
        "away_rest_days": away_data["rest_days"],
        "rest_days_diff": home_data["rest_days"] - away_data["rest_days"],
        "match_month": 0,
        "home_points_last_3": home_data["points_last_5"],
        "away_points_last_3": away_data["points_last_5"],
        "home_goals_for_last_3": home_data["goals_for_last_5"],
        "away_goals_for_last_3": away_data["goals_for_last_5"],
        "home_goals_against_last_3": home_data["goals_against_last_5"],
        "away_goals_against_last_3": away_data["goals_against_last_5"],
        "home_goal_diff_last_3": home_data["goals_for_last_5"] - home_data["goals_against_last_5"],
        "away_goal_diff_last_3": away_data["goals_for_last_5"] - away_data["goals_against_last_5"],
        "home_win_rate_last_3": home_data["wins_last_5"] / 5.0,
        "away_win_rate_last_3": away_data["wins_last_5"] / 5.0,
        "points_diff_last_3": home_data["points_last_5"] - away_data["points_last_5"],
        "goal_diff_form_last_3": (
            (home_data["goals_for_last_5"] - home_data["goals_against_last_5"])
            - (away_data["goals_for_last_5"] - away_data["goals_against_last_5"])
        ),
        "home_points_last_5": home_data["points_last_5"],
        "away_points_last_5": away_data["points_last_5"],
        "home_goals_for_last_5": home_data["goals_for_last_5"],
        "away_goals_for_last_5": away_data["goals_for_last_5"],
        "home_goals_against_last_5": home_data["goals_against_last_5"],
        "away_goals_against_last_5": away_data["goals_against_last_5"],
        "home_goal_diff_last_5": home_data["goals_for_last_5"] - home_data["goals_against_last_5"],
        "away_goal_diff_last_5": away_data["goals_for_last_5"] - away_data["goals_against_last_5"],
        "home_win_rate_last_5": home_data["wins_last_5"] / 5.0,
        "away_win_rate_last_5": away_data["wins_last_5"] / 5.0,
        "points_diff_last_5": home_data["points_last_5"] - away_data["points_last_5"],
        "goal_diff_form_last_5": (
            (home_data["goals_for_last_5"] - home_data["goals_against_last_5"])
            - (away_data["goals_for_last_5"] - away_data["goals_against_last_5"])
        ),
    }
    return pd.DataFrame([row])


def predict_match(
    home_team: str,
    away_team: str,
    provider: LiveDataProvider | None = None,
    cache: CacheManager | None = None,
    model_name: str = "logistic_regression",
) -> dict[str, Any]:
    provider = provider or PlaceholderLiveDataProvider()
    cache = cache or CacheManager()

    home_key = home_team
    away_key = away_team
    h2h_key = f"{home_team}__{away_team}"

    home_data = cache.load("team_form", home_key, CACHE_TTL_HOURS["team_form"])
    if home_data is None:
        home_data = asdict(provider.get_team_recent_form(home_team))
        cache.store("team_form", home_key, home_data)

    away_data = cache.load("team_form", away_key, CACHE_TTL_HOURS["team_form"])
    if away_data is None:
        away_data = asdict(provider.get_team_recent_form(away_team))
        cache.store("team_form", away_key, away_data)

    h2h_data = cache.load("head_to_head", h2h_key, CACHE_TTL_HOURS["head_to_head"])
    if h2h_data is None:
        h2h_data = asdict(provider.get_head_to_head_summary(home_team, away_team))
        cache.store("head_to_head", h2h_key, h2h_data)

    model = joblib.load(_model_path(model_name))
    X_live = _build_live_feature_row(home_data, away_data, h2h_data)
    prediction = model.predict(X_live)[0]

    response: dict[str, Any] = {
        "season": TARGET_SEASON,
        "home_team": home_team,
        "away_team": away_team,
        "prediction": prediction,
        "features_used": X_live.to_dict(orient="records")[0],
        "data_summary": {
            "home_recent_form": home_data,
            "away_recent_form": away_data,
            "head_to_head": h2h_data,
        },
    }

    if hasattr(model, "predict_proba"):
        classes = list(model.classes_)
        probabilities = model.predict_proba(X_live)[0]
        response["probabilities"] = dict(zip(classes, probabilities))

    return response
