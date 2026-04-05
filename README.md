# EPL 2025/26 Match Outcome Prediction

Python project for predicting English Premier League match outcomes for the 2025/26 season. The model is trained on historical EPL data, while each prediction uses fresh pre-match context for the two requested teams. A graphical interface can be added later on top of the prediction service.

## Scope

- Competition: English Premier League
- Prediction season: 2025/26 only
- Training data: historical EPL data from prior seasons
- Target: `H` / `D` / `A` for home win, draw, away win
- Constraint: use only information available before kickoff

## What This Starter Includes

- Historical CSV training pipeline
- Match table cleaning and schema normalization
- Rolling pre-match feature engineering
- Season-aware train/validation/test split
- Baseline models
- Logistic Regression and Random Forest training
- Metric reporting and artifact export
- Prediction service skeleton for 2025/26 fixtures
- Local cache skeleton for reducing repeated API calls

## Suggested Dataset

Use historical EPL CSV files from:

- `football-data.co.uk`: https://www.football-data.co.uk/data.php

Place season CSV files into:

```text
data/raw/
```

The pipeline expects columns that can be mapped to:

- `Date`
- `HomeTeam`
- `AwayTeam`
- `FTHG`
- `FTAG`
- `FTR`

These are standard columns in football-data.co.uk match files.

For the live 2025/26 prediction flow, the project will later call an external football API to pull:

- each team's last 5 matches
- recent head-to-head results
- rest days before the target fixture
- optional standings or form summaries

## Project Structure

```text
.
├── data/
│   ├── raw/
│   ├── interim/
│   └── processed/
├── outputs/
│   ├── figures/
│   ├── models/
│   └── tables/
├── cache/
│   ├── head_to_head/
│   └── team_form/
├── src/
│   ├── __init__.py
│   ├── cache_manager.py
│   ├── config.py
│   ├── data_loader.py
│   ├── evaluate.py
│   ├── features.py
│   ├── live_data_provider.py
│   ├── predict_service.py
│   ├── train.py
│   └── utils.py
├── main.py
├── requirements.txt
└── epl_project_draft.txt
```

## Workflow

1. Add historical season CSVs to `data/raw/`
2. Run `python3 main.py train`
3. Review metrics under `outputs/tables/`
4. Review trained artifacts under `outputs/models/`
5. Use `python3 main.py predict --home TEAM --away TEAM`
6. Iterate on feature logic and API integration

## Feature Design

The training pipeline creates pre-match features such as:

- rolling points over last 3 and 5 matches
- rolling goals scored and conceded
- rolling goal difference
- rolling win rate
- rest days
- current rank proxy based on cumulative points before the match
- rank difference
- match month

The prediction service is designed to combine the trained model with fresh 2025/26 match context for the requested teams. The first live prediction version will focus on:

- last 5 match results for each team
- recent head-to-head results
- rest days before the fixture

The project avoids leakage by computing features from information available before the current fixture.

## Modeling Approach

Baselines:

- most frequent class
- always home win

Machine learning models:

- multinomial logistic regression
- random forest classifier

## Validation Design

The historical training split is season-aware rather than randomly shuffled.

Default training split:

- train: `2015-2016` to `2022-2023`
- validation: `2023-2024`
- test: `2024-2025`

You can edit these values in `src/config.py`.

The target prediction season is configured separately as `2025-2026`.

## Output Files

After training, the project writes:

- `outputs/tables/model_metrics.csv`
- `outputs/tables/test_predictions.csv`
- `outputs/models/logistic_regression.joblib`
- `outputs/models/random_forest.joblib`

The prediction service will also use local cache files under `cache/` so repeated requests for the same teams do not call the API unnecessarily.

## Environment Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Live Data Setup

The live prediction service uses the current-season EPL CSV from `football-data.co.uk`.

On the first prediction run, the provider downloads:

- `https://www.football-data.co.uk/mmz4281/2526/E0.csv`

It refreshes the file when the local copy is older than six hours.

The live provider is intentionally limited to:

- upcoming EPL 2025/26 fixtures found in the current-season CSV
- each team's last 5 finished EPL matches from the same season
- recent head-to-head results computed from the historical training data plus finished 2025/26 matches
- rest days based on the target fixture date

## Run

```bash
python3 main.py fetch-data
python3 main.py train
python3 main.py predict --home Arsenal --away Chelsea
python3 main.py gui
```

If the same fixture context has already been fetched recently, the prediction flow reuses local cache files under `cache/` instead of repeating the same data pull logic.

## GUI

The local GUI runs on Flask with a SQLite backend.

Features included in V1:

- clean web form for home and away team input
- prediction result page with probability breakdown
- backend storage of each prediction request
- history page for previously stored predictions
- auto-refreshing timeline on the homepage

Start the app with:

```bash
python3 main.py gui
```

Then open:

```text
http://127.0.0.1:5000
```

## Next Steps

- wire in a real football API provider
- map live API responses into the existing feature schema
- add cache invalidation rules and TTLs
- add xG or shot-based features
- build a simple GUI around the prediction service

## Resume-Oriented Goal

Once real data is loaded and evaluated, this project should support a bullet like:

Built an EPL 2025/26 match prediction pipeline trained on historical league data and enriched with fresh pre-match team context, including recent form, head-to-head results, and rest-day features.

Evaluated baseline and machine learning models on season-based holdout data and designed a cached prediction service to reduce repeated API calls during live fixture prediction.
