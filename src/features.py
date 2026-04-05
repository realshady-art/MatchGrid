from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np
import pandas as pd

from src.config import AWAY_TEAM_COLUMN, DATE_COLUMN, HOME_TEAM_COLUMN, ROLLING_WINDOWS, SEASON_COLUMN, TARGET_COLUMN


def _points_from_result(result: str, side: str) -> int:
    if result == "D":
        return 1
    if side == "home":
        return 3 if result == "H" else 0
    return 3 if result == "A" else 0


def get_feature_columns() -> list[str]:
    feature_columns = [
        "home_rank_before_match",
        "away_rank_before_match",
        "rank_diff",
        "home_rest_days",
        "away_rest_days",
        "rest_days_diff",
        "match_month",
        "head_to_head_home_points_last_3",
        "head_to_head_away_points_last_3",
        "head_to_head_home_goal_diff_last_3",
    ]

    for window in ROLLING_WINDOWS:
        feature_columns.extend(
            [
                f"home_points_last_{window}",
                f"away_points_last_{window}",
                f"home_goals_for_last_{window}",
                f"away_goals_for_last_{window}",
                f"home_goals_against_last_{window}",
                f"away_goals_against_last_{window}",
                f"home_goal_diff_last_{window}",
                f"away_goal_diff_last_{window}",
                f"home_win_rate_last_{window}",
                f"away_win_rate_last_{window}",
                f"points_diff_last_{window}",
                f"goal_diff_form_last_{window}",
            ]
        )

    return feature_columns


def build_long_team_history(matches: pd.DataFrame) -> pd.DataFrame:
    home = pd.DataFrame(
        {
            "season": matches[SEASON_COLUMN],
            "date": matches[DATE_COLUMN],
            "team": matches[HOME_TEAM_COLUMN],
            "opponent": matches[AWAY_TEAM_COLUMN],
            "is_home": 1,
            "goals_for": matches["home_goals"],
            "goals_against": matches["away_goals"],
            "result": matches[TARGET_COLUMN],
        }
    )
    away = pd.DataFrame(
        {
            "season": matches[SEASON_COLUMN],
            "date": matches[DATE_COLUMN],
            "team": matches[AWAY_TEAM_COLUMN],
            "opponent": matches[HOME_TEAM_COLUMN],
            "is_home": 0,
            "goals_for": matches["away_goals"],
            "goals_against": matches["home_goals"],
            "result": matches[TARGET_COLUMN],
        }
    )

    home["points"] = home["result"].map(lambda value: _points_from_result(value, "home"))
    away["points"] = away["result"].map(lambda value: _points_from_result(value, "away"))

    team_history = (
        pd.concat([home, away], ignore_index=True)
        .sort_values(["season", "team", "date"])
        .reset_index(drop=True)
    )
    team_history["goal_diff"] = team_history["goals_for"] - team_history["goals_against"]
    team_history["win"] = np.where(
        ((team_history["is_home"] == 1) & (team_history["result"] == "H"))
        | ((team_history["is_home"] == 0) & (team_history["result"] == "A")),
        1,
        0,
    )

    group_keys = [team_history["season"], team_history["team"]]
    grouped = team_history.groupby(["season", "team"], group_keys=False)
    for window in ROLLING_WINDOWS:
        shifted_points = grouped["points"].shift(1)
        shifted_goals_for = grouped["goals_for"].shift(1)
        shifted_goals_against = grouped["goals_against"].shift(1)
        shifted_goal_diff = grouped["goal_diff"].shift(1)
        shifted_win = grouped["win"].shift(1)

        team_history[f"points_last_{window}"] = (
            shifted_points.groupby(group_keys).rolling(window, min_periods=1).sum().reset_index(level=[0, 1], drop=True)
        )
        team_history[f"goals_for_last_{window}"] = (
            shifted_goals_for.groupby(group_keys).rolling(window, min_periods=1).sum().reset_index(level=[0, 1], drop=True)
        )
        team_history[f"goals_against_last_{window}"] = (
            shifted_goals_against.groupby(group_keys).rolling(window, min_periods=1).sum().reset_index(level=[0, 1], drop=True)
        )
        team_history[f"goal_diff_last_{window}"] = (
            shifted_goal_diff.groupby(group_keys).rolling(window, min_periods=1).sum().reset_index(level=[0, 1], drop=True)
        )
        team_history[f"win_rate_last_{window}"] = (
            shifted_win.groupby(group_keys).rolling(window, min_periods=1).mean().reset_index(level=[0, 1], drop=True)
        )

    team_history["rest_days"] = grouped["date"].diff().dt.days
    team_history["cumulative_points_before_match"] = grouped["points"].cumsum() - team_history["points"]
    team_history["match_count_before_match"] = grouped.cumcount()
    return team_history


def _add_rank_features(team_history: pd.DataFrame) -> pd.DataFrame:
    enriched = team_history.copy()
    enriched["rank_before_match"] = (
        enriched.groupby(["season", "date"])["cumulative_points_before_match"].rank(method="min", ascending=False)
    )
    return enriched


def _head_to_head_from_home_perspective(match_row: pd.Series, team_name: str) -> tuple[int, int]:
    if match_row[HOME_TEAM_COLUMN] == team_name:
        goals_for = match_row["home_goals"]
        goals_against = match_row["away_goals"]
        result = match_row[TARGET_COLUMN]
        points = _points_from_result(result, "home")
        return points, goals_for - goals_against

    goals_for = match_row["away_goals"]
    goals_against = match_row["home_goals"]
    result = match_row[TARGET_COLUMN]
    points = _points_from_result(result, "away")
    return points, goals_for - goals_against


def add_head_to_head_features(matches: pd.DataFrame) -> pd.DataFrame:
    history: defaultdict[tuple[str, tuple[str, str]], list[pd.Series]] = defaultdict(list)
    home_points: list[int] = []
    away_points: list[int] = []
    home_goal_diff: list[int] = []

    for _, row in matches.sort_values([SEASON_COLUMN, DATE_COLUMN]).iterrows():
        pair_key = tuple(sorted((row[HOME_TEAM_COLUMN], row[AWAY_TEAM_COLUMN])))
        season_pair_key = (row[SEASON_COLUMN], pair_key)
        prior = history[season_pair_key][-3:]

        current_home_points = 0
        current_away_points = 0
        current_home_goal_diff = 0

        for prior_match in prior:
            points_for_home, goal_diff_for_home = _head_to_head_from_home_perspective(
                prior_match, row[HOME_TEAM_COLUMN]
            )
            points_for_away, _ = _head_to_head_from_home_perspective(prior_match, row[AWAY_TEAM_COLUMN])
            current_home_points += points_for_home
            current_away_points += points_for_away
            current_home_goal_diff += goal_diff_for_home

        home_points.append(current_home_points)
        away_points.append(current_away_points)
        home_goal_diff.append(current_home_goal_diff)
        history[season_pair_key].append(row.copy())

    enriched = matches.copy()
    enriched["head_to_head_home_points_last_3"] = home_points
    enriched["head_to_head_away_points_last_3"] = away_points
    enriched["head_to_head_home_goal_diff_last_3"] = home_goal_diff
    return enriched


def build_feature_table(matches: pd.DataFrame) -> pd.DataFrame:
    matches = matches.sort_values([SEASON_COLUMN, DATE_COLUMN]).reset_index(drop=True)
    team_history = _add_rank_features(build_long_team_history(matches))

    home_features = team_history[team_history["is_home"] == 1].copy().add_prefix("home_")
    away_features = team_history[team_history["is_home"] == 0].copy().add_prefix("away_")

    feature_table = matches.copy()
    feature_table = feature_table.merge(
        home_features,
        left_on=[SEASON_COLUMN, DATE_COLUMN, HOME_TEAM_COLUMN, AWAY_TEAM_COLUMN],
        right_on=["home_season", "home_date", "home_team", "home_opponent"],
        how="left",
    )
    feature_table = feature_table.merge(
        away_features,
        left_on=[SEASON_COLUMN, DATE_COLUMN, AWAY_TEAM_COLUMN, HOME_TEAM_COLUMN],
        right_on=["away_season", "away_date", "away_team", "away_opponent"],
        how="left",
    )

    for window in ROLLING_WINDOWS:
        feature_table[f"points_diff_last_{window}"] = (
            feature_table[f"home_points_last_{window}"] - feature_table[f"away_points_last_{window}"]
        )
        feature_table[f"goal_diff_form_last_{window}"] = (
            feature_table[f"home_goal_diff_last_{window}"] - feature_table[f"away_goal_diff_last_{window}"]
        )

    feature_table["rank_diff"] = feature_table["away_rank_before_match"] - feature_table["home_rank_before_match"]
    feature_table["rest_days_diff"] = feature_table["home_rest_days"] - feature_table["away_rest_days"]
    feature_table["match_month"] = feature_table[DATE_COLUMN].dt.month
    feature_table = add_head_to_head_features(feature_table)

    numeric_columns = feature_table.select_dtypes(include=["number"]).columns
    feature_table[numeric_columns] = feature_table[numeric_columns].fillna(0)
    return feature_table


def get_model_features(feature_table: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    X = feature_table[get_feature_columns()].copy()
    y = feature_table[TARGET_COLUMN].copy()
    return X, y
