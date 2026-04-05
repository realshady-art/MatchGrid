import argparse
import json
from pathlib import Path

from src.config import OUTPUT_TABLES_DIR
from src.predict_service import predict_match
from src.train import run_training_pipeline


def run_train() -> None:
    metrics = run_training_pipeline()
    metrics_path = Path(OUTPUT_TABLES_DIR) / "model_metrics.csv"
    print("Training complete.")
    print(f"Metrics saved to: {metrics_path}")
    print(metrics.to_string(index=False))


def run_predict(home_team: str, away_team: str) -> None:
    prediction = predict_match(home_team=home_team, away_team=away_team)
    print(json.dumps(prediction, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="EPL 2025/26 match prediction pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("train", help="Train historical EPL models")

    predict_parser = subparsers.add_parser("predict", help="Predict a 2025/26 EPL fixture")
    predict_parser.add_argument("--home", required=True, dest="home_team", help="Home team name")
    predict_parser.add_argument("--away", required=True, dest="away_team", help="Away team name")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "train":
        run_train()
    elif args.command == "predict":
        run_predict(home_team=args.home_team, away_team=args.away_team)


if __name__ == "__main__":
    main()
