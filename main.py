from pathlib import Path

from src.config import OUTPUT_TABLES_DIR
from src.train import run_training_pipeline


def main() -> None:
    metrics = run_training_pipeline()
    metrics_path = Path(OUTPUT_TABLES_DIR) / "model_metrics.csv"
    print("Training complete.")
    print(f"Metrics saved to: {metrics_path}")
    print(metrics.to_string(index=False))


if __name__ == "__main__":
    main()
