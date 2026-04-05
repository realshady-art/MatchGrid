from pathlib import Path

import pandas as pd
from sklearn.metrics import accuracy_score, precision_recall_fscore_support

from src.config import OUTPUT_TABLES_DIR
from src.utils import ensure_directories


def build_metrics_row(model_name: str, y_true: pd.Series, y_pred: pd.Series, split_name: str) -> dict[str, float | str]:
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true,
        y_pred,
        average="macro",
        zero_division=0,
    )
    return {
        "model": model_name,
        "split": split_name,
        "accuracy": accuracy_score(y_true, y_pred),
        "macro_precision": precision,
        "macro_recall": recall,
        "macro_f1": f1,
    }


def save_metrics(metrics: pd.DataFrame) -> Path:
    ensure_directories([Path(OUTPUT_TABLES_DIR)])
    output_path = Path(OUTPUT_TABLES_DIR) / "model_metrics.csv"
    metrics.to_csv(output_path, index=False)
    return output_path


def save_predictions(predictions: pd.DataFrame) -> Path:
    ensure_directories([Path(OUTPUT_TABLES_DIR)])
    output_path = Path(OUTPUT_TABLES_DIR) / "test_predictions.csv"
    predictions.to_csv(output_path, index=False)
    return output_path
