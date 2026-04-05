# EPL Match Outcome Prediction

Python starter project for predicting English Premier League match outcomes from pre-match team information. The current scope is the machine learning workflow only. A graphical interface can be added later on top of the trained pipeline.

## Scope

- Competition: English Premier League
- Time range: approximately the last 10 seasons
- Target: `H` / `D` / `A` for home win, draw, away win
- Constraint: use only information available before kickoff

## What This Starter Includes

- Local CSV data loading
- Match table cleaning and schema normalization
- Rolling pre-match feature engineering
- Season-aware train/validation/test split
- Baseline models
- Logistic Regression and Random Forest training
- Metric reporting and artifact export

## Suggested Dataset

Use EPL CSV files from:

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
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── data_loader.py
│   ├── evaluate.py
│   ├── features.py
│   ├── train.py
│   └── utils.py
├── main.py
├── requirements.txt
└── epl_project_draft.txt
```

## Workflow

1. Add season CSVs to `data/raw/`
2. Run `python3 main.py`
3. Review metrics under `outputs/tables/`
4. Review trained artifacts under `outputs/models/`
5. Iterate on features and validation strategy

## Feature Design In This Starter

The first version creates only pre-match features:

- rolling points over last 3 and 5 matches
- rolling goals scored and conceded
- rolling goal difference
- rolling win rate
- rest days
- current rank proxy based on cumulative points before the match
- rank difference
- match month

This starter intentionally avoids leakage by computing features from each team's history before the current fixture.

## Modeling Approach

Baselines:

- most frequent class
- always home win

Machine learning models:

- multinomial logistic regression
- random forest classifier

## Validation Design

The split is season-aware rather than randomly shuffled.

Default split:

- train: `2015-2016` to `2021-2022`
- validation: `2022-2023`
- test: `2023-2024`

You can edit these values in `src/config.py`.

## Output Files

After training, the project writes:

- `outputs/tables/model_metrics.csv`
- `outputs/tables/test_predictions.csv`
- `outputs/models/logistic_regression.joblib`
- `outputs/models/random_forest.joblib`

## Environment Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python3 main.py
```

## Next Steps

- add xG or shot-based features
- add odds-based baselines
- compare rolling windows
- add model calibration
- build a simple GUI around the prediction pipeline

## Resume-Oriented Goal

Once real data is loaded and evaluated, this project should support a bullet like:

Built an end-to-end EPL match prediction pipeline using 10 seasons of historical match data, engineering rolling form, goal-differential, and standings-based features to predict win/draw/loss outcomes.

Evaluated baseline and machine learning models on season-based holdout data, achieving X% test accuracy and identifying recent form, rank difference, and home advantage as the strongest predictors.
