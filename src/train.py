from pathlib import Path
import json

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.config import (
    OUTPUT_MODELS_DIR,
    OUTPUT_TABLES_DIR,
    OUTPUT_DIR,
    TEST_SEASONS,
    TRAIN_SEASONS,
    VALIDATION_SEASONS,
    SEASON_COLUMN,
    DATE_COLUMN,
    HOME_TEAM_COLUMN,
    AWAY_TEAM_COLUMN,
    MODEL_RANDOM_STATE,
)
from src.data_loader import load_all_raw_data
from src.evaluate import build_metrics_row, save_metrics, save_predictions
from src.features import build_feature_table, get_feature_columns, get_model_features
from src.utils import ensure_directories


def _split_by_season(feature_table: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train = feature_table[feature_table[SEASON_COLUMN].isin(TRAIN_SEASONS)].copy()
    validation = feature_table[feature_table[SEASON_COLUMN].isin(VALIDATION_SEASONS)].copy()
    test = feature_table[feature_table[SEASON_COLUMN].isin(TEST_SEASONS)].copy()

    if train.empty or validation.empty or test.empty:
        raise ValueError(
            "One or more seasonal splits are empty. Check the CSV season names or update src/config.py."
        )
    return train, validation, test


def _baseline_predictions(y: pd.Series) -> dict[str, pd.Series]:
    most_frequent = y.mode().iat[0]
    return {
        "most_frequent": pd.Series([most_frequent] * len(y), index=y.index),
        "always_home_win": pd.Series(["H"] * len(y), index=y.index),
    }


def _build_models() -> dict[str, object]:
    return {
        "logistic_regression": Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "model",
                    LogisticRegression(
                        max_iter=2000,
                        random_state=MODEL_RANDOM_STATE,
                    ),
                ),
            ]
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=300,
            max_depth=10,
            min_samples_leaf=3,
            random_state=MODEL_RANDOM_STATE,
        ),
    }


def run_training_pipeline() -> pd.DataFrame:
    ensure_directories([Path(OUTPUT_DIR), Path(OUTPUT_MODELS_DIR), Path(OUTPUT_TABLES_DIR)])

    matches = load_all_raw_data()
    feature_table = build_feature_table(matches)
    train_df, validation_df, test_df = _split_by_season(feature_table)

    X_train, y_train = get_model_features(train_df)
    X_validation, y_validation = get_model_features(validation_df)
    X_test, y_test = get_model_features(test_df)

    metrics_rows: list[dict[str, float | str]] = []

    for baseline_name, baseline_pred in _baseline_predictions(y_validation).items():
        metrics_rows.append(build_metrics_row(baseline_name, y_validation, baseline_pred, "validation"))
    for baseline_name, baseline_pred in _baseline_predictions(y_test).items():
        metrics_rows.append(build_metrics_row(baseline_name, y_test, baseline_pred, "test"))

    predictions_export = test_df[[DATE_COLUMN, HOME_TEAM_COLUMN, AWAY_TEAM_COLUMN, "home_goals", "away_goals", "result"]].copy()

    for model_name, model in _build_models().items():
        model.fit(X_train, y_train)
        validation_pred = model.predict(X_validation)
        test_pred = model.predict(X_test)

        metrics_rows.append(build_metrics_row(model_name, y_validation, validation_pred, "validation"))
        metrics_rows.append(build_metrics_row(model_name, y_test, test_pred, "test"))

        model_path = Path(OUTPUT_MODELS_DIR) / f"{model_name}.joblib"
        joblib.dump(model, model_path)
        predictions_export[f"{model_name}_pred"] = test_pred

    feature_schema_path = Path(OUTPUT_MODELS_DIR) / "feature_columns.json"
    feature_schema_path.write_text(json.dumps(get_feature_columns(), indent=2), encoding="utf-8")

    metrics = pd.DataFrame(metrics_rows).sort_values(["split", "accuracy"], ascending=[True, False]).reset_index(drop=True)
    save_metrics(metrics)
    save_predictions(predictions_export)
    return metrics
