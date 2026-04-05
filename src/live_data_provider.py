from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol

import pandas as pd
import requests

from src.config import (
    DATE_COLUMN,
    HOME_TEAM_COLUMN,
    AWAY_TEAM_COLUMN,
    LIVE_COMPETITION_CODE,
    LIVE_DATA_DIR,
    LIVE_DATA_FILENAME,
    LIVE_DATA_URL,
    LIVE_SEASON_CODE,
    TARGET_COLUMN,
    TARGET_SEASON,
)
from src.data_loader import load_all_raw_data
from src.features import _points_from_result
from src.utils import ensure_directories


@dataclass
class FixtureContext:
    home_team: str
    away_team: str
    home_team_id: int
    away_team_id: int
    fixture_utc_date: str
    season: str
    home_rank: int
    away_rank: int


@dataclass
class TeamRecentForm:
    team: str
    team_id: int
    wins_last_3: int
    draws_last_3: int
    losses_last_3: int
    points_last_3: int
    goals_for_last_3: int
    goals_against_last_3: int
    wins_last_5: int
    draws_last_5: int
    losses_last_5: int
    points_last_5: int
    goals_for_last_5: int
    goals_against_last_5: int
    rest_days: int
    rank: int
    last_match_utc_date: str


@dataclass
class HeadToHeadSummary:
    home_team: str
    away_team: str
    home_points_last_3: int
    away_points_last_3: int
    home_goal_diff_last_3: int
    sample_size: int


class LiveDataProvider(Protocol):
    def get_fixture_context(self, home_team: str, away_team: str) -> FixtureContext:
        ...

    def get_team_recent_form(self, team_name: str, team_id: int, fixture_utc_date: str) -> TeamRecentForm:
        ...

    def get_head_to_head_summary(
        self,
        home_team: str,
        away_team: str,
        home_team_id: int,
        away_team_id: int,
        fixture_utc_date: str,
    ) -> HeadToHeadSummary:
        ...


class LiveDataProviderError(RuntimeError):
    pass


class FootballDataCsvProvider:
    """Live EPL data provider backed by football-data.co.uk current-season CSV."""

    TEAM_ALIASES = {
        "man city": "Man City",
        "manchester city": "Man City",
        "man utd": "Man United",
        "manchester united": "Man United",
        "newcastle": "Newcastle",
        "newcastle united": "Newcastle",
        "spurs": "Tottenham",
        "tottenham hotspur": "Tottenham",
        "wolves": "Wolves",
        "wolverhampton": "Wolves",
        "wolverhampton wanderers": "Wolves",
        "nottingham forest": "Nott'm Forest",
        "forest": "Nott'm Forest",
    }

    def __init__(self, live_csv_path: Path | None = None) -> None:
        self.live_csv_path = live_csv_path or (LIVE_DATA_DIR / LIVE_DATA_FILENAME)
        self._live_df: pd.DataFrame | None = None
        self._historical_df: pd.DataFrame | None = None
        self._team_ids: dict[str, int] = {}

    def available_teams(self) -> list[str]:
        teams = sorted(set(self._get_live_df()[HOME_TEAM_COLUMN]).union(set(self._get_live_df()[AWAY_TEAM_COLUMN])))
        return teams

    def get_fixture_context(self, home_team: str, away_team: str) -> FixtureContext:
        live_df = self._get_live_df()
        resolved_home = self._resolve_team_name(home_team)
        resolved_away = self._resolve_team_name(away_team)
        fixture = live_df[
            (live_df[HOME_TEAM_COLUMN] == resolved_home)
            & (live_df[AWAY_TEAM_COLUMN] == resolved_away)
            & (live_df[TARGET_COLUMN].isna())
        ].sort_values(DATE_COLUMN)
        if fixture.empty:
            latest_completed = live_df.loc[live_df[TARGET_COLUMN].notna(), DATE_COLUMN].max()
            if pd.isna(latest_completed):
                raise LiveDataProviderError("Live season file has no completed matches to anchor a prediction date.")
            synthetic_date = latest_completed + pd.Timedelta(days=7)
            standings = self._compute_current_standings(live_df, synthetic_date)
            return FixtureContext(
                home_team=resolved_home,
                away_team=resolved_away,
                home_team_id=self._team_id(resolved_home),
                away_team_id=self._team_id(resolved_away),
                fixture_utc_date=self._to_utc_date_string(synthetic_date),
                season=TARGET_SEASON,
                home_rank=standings.get(resolved_home, 0),
                away_rank=standings.get(resolved_away, 0),
            )

        row = fixture.iloc[0]
        standings = self._compute_current_standings(live_df, row[DATE_COLUMN])
        home_name = str(row[HOME_TEAM_COLUMN])
        away_name = str(row[AWAY_TEAM_COLUMN])

        return FixtureContext(
            home_team=home_name,
            away_team=away_name,
            home_team_id=self._team_id(home_name),
            away_team_id=self._team_id(away_name),
            fixture_utc_date=self._to_utc_date_string(row[DATE_COLUMN]),
            season=TARGET_SEASON,
            home_rank=standings.get(home_name, 0),
            away_rank=standings.get(away_name, 0),
        )

    def get_team_recent_form(self, team_name: str, team_id: int, fixture_utc_date: str) -> TeamRecentForm:
        del team_id
        live_df = self._get_live_df()
        fixture_date = self._parse_utc(fixture_utc_date)
        finished = self._team_matches_before_fixture(live_df, team_name, fixture_date)
        if finished.empty:
            raise LiveDataProviderError(f"No completed {TARGET_SEASON} matches found for {team_name}.")

        last_5 = finished.head(5)
        last_3 = finished.head(3)

        summary_5 = self._summarize_team_matches(last_5, team_name)
        summary_3 = self._summarize_team_matches(last_3, team_name)

        last_match_date = last_5.iloc[0][DATE_COLUMN]
        rest_days = max((fixture_date.date() - last_match_date.date()).days, 0)
        standings = self._compute_current_standings(live_df, fixture_date)

        return TeamRecentForm(
            team=team_name,
            team_id=self._team_id(team_name),
            wins_last_3=summary_3["wins"],
            draws_last_3=summary_3["draws"],
            losses_last_3=summary_3["losses"],
            points_last_3=summary_3["points"],
            goals_for_last_3=summary_3["goals_for"],
            goals_against_last_3=summary_3["goals_against"],
            wins_last_5=summary_5["wins"],
            draws_last_5=summary_5["draws"],
            losses_last_5=summary_5["losses"],
            points_last_5=summary_5["points"],
            goals_for_last_5=summary_5["goals_for"],
            goals_against_last_5=summary_5["goals_against"],
            rest_days=rest_days,
            rank=standings.get(team_name, 0),
            last_match_utc_date=self._to_utc_date_string(last_match_date),
        )

    def get_head_to_head_summary(
        self,
        home_team: str,
        away_team: str,
        home_team_id: int,
        away_team_id: int,
        fixture_utc_date: str,
    ) -> HeadToHeadSummary:
        del home_team_id, away_team_id
        historical = self._get_historical_df()
        fixture_date = self._parse_utc(fixture_utc_date)

        mask = (
            (
                (historical[HOME_TEAM_COLUMN] == home_team)
                & (historical[AWAY_TEAM_COLUMN] == away_team)
            )
            | (
                (historical[HOME_TEAM_COLUMN] == away_team)
                & (historical[AWAY_TEAM_COLUMN] == home_team)
            )
        ) & (historical[DATE_COLUMN] < fixture_date)

        recent = historical.loc[mask].sort_values(DATE_COLUMN, ascending=False).head(3)

        home_points = 0
        away_points = 0
        home_goal_diff = 0
        for _, row in recent.iterrows():
            if row[HOME_TEAM_COLUMN] == home_team:
                home_side = "home"
                away_side = "away"
                home_goals = row["home_goals"]
                away_goals = row["away_goals"]
            else:
                home_side = "away"
                away_side = "home"
                home_goals = row["away_goals"]
                away_goals = row["home_goals"]

            home_points += _points_from_result(row[TARGET_COLUMN], home_side)
            away_points += _points_from_result(row[TARGET_COLUMN], away_side)
            home_goal_diff += home_goals - away_goals

        return HeadToHeadSummary(
            home_team=home_team,
            away_team=away_team,
            home_points_last_3=home_points,
            away_points_last_3=away_points,
            home_goal_diff_last_3=home_goal_diff,
            sample_size=len(recent),
        )

    def _get_live_df(self) -> pd.DataFrame:
        if self._live_df is None:
            self._refresh_live_csv_if_needed()
            df = pd.read_csv(self.live_csv_path)
            df = self._normalize_match_frame(df)
            df["season"] = TARGET_SEASON
            self._live_df = df
        return self._live_df

    def _get_historical_df(self) -> pd.DataFrame:
        if self._historical_df is None:
            historical = load_all_raw_data()
            live_finished = self._get_live_df().loc[self._get_live_df()[TARGET_COLUMN].notna()].copy()
            combined = pd.concat([historical, live_finished], ignore_index=True)
            combined = combined.sort_values(DATE_COLUMN).reset_index(drop=True)
            self._historical_df = combined
        return self._historical_df

    def _refresh_live_csv_if_needed(self) -> None:
        ensure_directories([LIVE_DATA_DIR])
        refresh = True
        if self.live_csv_path.exists():
            age = datetime.now(timezone.utc) - datetime.fromtimestamp(
                self.live_csv_path.stat().st_mtime,
                tz=timezone.utc,
            )
            refresh = age > timedelta(hours=6)

        if refresh:
            response = requests.get(LIVE_DATA_URL, timeout=20)
            response.raise_for_status()
            self.live_csv_path.write_text(response.text, encoding="utf-8")

    def _compute_current_standings(self, live_df: pd.DataFrame, fixture_date: datetime | pd.Timestamp) -> dict[str, int]:
        if isinstance(fixture_date, pd.Timestamp):
            fixture_cutoff = fixture_date.to_pydatetime()
        else:
            fixture_cutoff = fixture_date

        completed = live_df[
            live_df[TARGET_COLUMN].notna() & (live_df[DATE_COLUMN] < fixture_cutoff)
        ].sort_values(DATE_COLUMN)

        table: dict[str, dict[str, int]] = {}
        for _, row in completed.iterrows():
            home = row[HOME_TEAM_COLUMN]
            away = row[AWAY_TEAM_COLUMN]
            table.setdefault(home, {"points": 0, "goal_diff": 0, "goals_for": 0})
            table.setdefault(away, {"points": 0, "goal_diff": 0, "goals_for": 0})

            home_goals = int(row["home_goals"])
            away_goals = int(row["away_goals"])

            table[home]["points"] += _points_from_result(row[TARGET_COLUMN], "home")
            table[away]["points"] += _points_from_result(row[TARGET_COLUMN], "away")

            table[home]["goal_diff"] += home_goals - away_goals
            table[away]["goal_diff"] += away_goals - home_goals
            table[home]["goals_for"] += home_goals
            table[away]["goals_for"] += away_goals

        ordered = sorted(
            table.items(),
            key=lambda item: (item[1]["points"], item[1]["goal_diff"], item[1]["goals_for"]),
            reverse=True,
        )
        return {team: idx + 1 for idx, (team, _) in enumerate(ordered)}

    def _team_matches_before_fixture(self, live_df: pd.DataFrame, team_name: str, fixture_date: datetime) -> pd.DataFrame:
        mask = (
            live_df[TARGET_COLUMN].notna()
            & (live_df[DATE_COLUMN] < fixture_date)
            & (
                (live_df[HOME_TEAM_COLUMN] == team_name)
                | (live_df[AWAY_TEAM_COLUMN] == team_name)
            )
        )
        return live_df.loc[mask].sort_values(DATE_COLUMN, ascending=False)

    def _summarize_team_matches(self, matches: pd.DataFrame, team_name: str) -> dict[str, int]:
        wins = draws = losses = goals_for = goals_against = 0
        for _, row in matches.iterrows():
            is_home = row[HOME_TEAM_COLUMN] == team_name
            team_goals = int(row["home_goals"] if is_home else row["away_goals"])
            opponent_goals = int(row["away_goals"] if is_home else row["home_goals"])
            goals_for += team_goals
            goals_against += opponent_goals
            if team_goals > opponent_goals:
                wins += 1
            elif team_goals < opponent_goals:
                losses += 1
            else:
                draws += 1

        return {
            "wins": wins,
            "draws": draws,
            "losses": losses,
            "points": wins * 3 + draws,
            "goals_for": goals_for,
            "goals_against": goals_against,
        }

    def _team_id(self, team_name: str) -> int:
        if not self._team_ids:
            teams = sorted(set(self._get_live_df()[HOME_TEAM_COLUMN]).union(set(self._get_live_df()[AWAY_TEAM_COLUMN])))
            self._team_ids = {team: idx + 1 for idx, team in enumerate(teams)}
        return self._team_ids[team_name]

    def _resolve_team_name(self, team_name: str) -> str:
        teams = sorted(set(self._get_live_df()[HOME_TEAM_COLUMN]).union(set(self._get_live_df()[AWAY_TEAM_COLUMN])))
        normalized_map = {team.casefold(): team for team in teams}
        alias = self.TEAM_ALIASES.get(team_name.casefold(), team_name)
        if alias.casefold() in normalized_map:
            return normalized_map[alias.casefold()]

        partial = [team for team in teams if alias.casefold() in team.casefold() or team.casefold() in alias.casefold()]
        if len(partial) == 1:
            return partial[0]

        raise LiveDataProviderError(f"Could not resolve team name from live season data: {team_name}")

    @staticmethod
    def _normalize_match_frame(df: pd.DataFrame) -> pd.DataFrame:
        required = ["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"]
        missing = [column for column in required if column not in df.columns]
        if missing:
            raise LiveDataProviderError(f"Live CSV missing required columns: {missing}")

        normalized = df[required].rename(
            columns={
                "Date": DATE_COLUMN,
                "HomeTeam": HOME_TEAM_COLUMN,
                "AwayTeam": AWAY_TEAM_COLUMN,
                "FTHG": "home_goals",
                "FTAG": "away_goals",
                "FTR": TARGET_COLUMN,
            }
        )
        normalized[DATE_COLUMN] = pd.to_datetime(normalized[DATE_COLUMN], dayfirst=True, errors="coerce")
        normalized[TARGET_COLUMN] = normalized[TARGET_COLUMN].astype("string").str.strip().str.upper()
        return normalized.dropna(subset=[DATE_COLUMN, HOME_TEAM_COLUMN, AWAY_TEAM_COLUMN]).reset_index(drop=True)

    @staticmethod
    def _parse_utc(value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None)

    @staticmethod
    def _to_utc_date_string(value: pd.Timestamp) -> str:
        dt = pd.Timestamp(value).to_pydatetime().replace(tzinfo=timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")
