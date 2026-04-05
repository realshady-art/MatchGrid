from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from src.config import FOOTBALL_DATA_API_BASE_URL, FOOTBALL_DATA_API_TOKEN, TARGET_SEASON


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


class FootballDataProvider:
    """Live EPL data provider backed by football-data.org API v4."""

    COMPETITION_CODE = "PL"
    SEASON_START_YEAR = 2025

    TEAM_ALIASES = {
        "arsenal": "arsenal fc",
        "aston villa": "aston villa fc",
        "bournemouth": "afc bournemouth",
        "brentford": "brentford fc",
        "brighton": "brighton & hove albion fc",
        "burnley": "burnley fc",
        "chelsea": "chelsea fc",
        "crystal palace": "crystal palace fc",
        "everton": "everton fc",
        "fulham": "fulham fc",
        "leeds": "leeds united fc",
        "liverpool": "liverpool fc",
        "man city": "manchester city fc",
        "manchester city": "manchester city fc",
        "man utd": "manchester united fc",
        "man united": "manchester united fc",
        "manchester united": "manchester united fc",
        "newcastle": "newcastle united fc",
        "newcastle united": "newcastle united fc",
        "nottingham forest": "nottingham forest fc",
        "forest": "nottingham forest fc",
        "spurs": "tottenham hotspur fc",
        "tottenham": "tottenham hotspur fc",
        "sunderland": "sunderland afc",
        "west ham": "west ham united fc",
        "wolves": "wolverhampton wanderers fc",
        "wolverhampton": "wolverhampton wanderers fc",
    }

    def __init__(self, api_token: str | None = None, base_url: str = FOOTBALL_DATA_API_BASE_URL) -> None:
        self.api_token = api_token or os.getenv("FOOTBALL_DATA_API_TOKEN") or FOOTBALL_DATA_API_TOKEN
        if not self.api_token:
            raise LiveDataProviderError(
                "Missing football-data.org API token. Set FOOTBALL_DATA_API_TOKEN before using live prediction."
            )
        self.base_url = base_url.rstrip("/")
        self._teams_cache: dict[str, dict[str, Any]] | None = None
        self._standings_cache: dict[int, int] | None = None
        self._scheduled_matches_cache: list[dict[str, Any]] | None = None
        self._finished_matches_cache: list[dict[str, Any]] | None = None

    def get_fixture_context(self, home_team: str, away_team: str) -> FixtureContext:
        home = self._resolve_team(home_team)
        away = self._resolve_team(away_team)

        scheduled_matches = self._get_scheduled_matches()
        fixture = self._find_next_fixture(scheduled_matches, home["id"], away["id"])
        if fixture is None:
            raise LiveDataProviderError(
                f"No scheduled EPL {TARGET_SEASON} fixture found for {home_team} vs {away_team}."
            )

        standings = self._get_standings()
        return FixtureContext(
            home_team=home["name"],
            away_team=away["name"],
            home_team_id=home["id"],
            away_team_id=away["id"],
            fixture_utc_date=fixture["utcDate"],
            season=TARGET_SEASON,
            home_rank=standings.get(home["id"], 0),
            away_rank=standings.get(away["id"], 0),
        )

    def get_team_recent_form(self, team_name: str, team_id: int, fixture_utc_date: str) -> TeamRecentForm:
        fixture_cutoff = fixture_utc_date[:10]
        params = {
            "season": str(self.SEASON_START_YEAR),
            "status": "FINISHED",
            "dateTo": fixture_cutoff,
            "limit": "5",
        }
        response = self._request_json(f"/teams/{team_id}/matches", params=params)
        matches = sorted(
            response.get("matches", []),
            key=lambda match: match["utcDate"],
            reverse=True,
        )
        if not matches:
            raise LiveDataProviderError(f"No finished {TARGET_SEASON} matches found for {team_name}.")

        summary_3 = self._summarize_recent_matches(matches[:3], team_id)
        summary_5 = self._summarize_recent_matches(matches[:5], team_id)

        last_match_dt = self._parse_utc(matches[0]["utcDate"])
        fixture_dt = self._parse_utc(fixture_utc_date)
        rest_days = max((fixture_dt - last_match_dt).days, 0)

        return TeamRecentForm(
            team=team_name,
            team_id=team_id,
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
            rank=self._get_standings().get(team_id, 0),
            last_match_utc_date=matches[0]["utcDate"],
        )

    def get_head_to_head_summary(
        self,
        home_team: str,
        away_team: str,
        home_team_id: int,
        away_team_id: int,
        fixture_utc_date: str,
    ) -> HeadToHeadSummary:
        fixture_dt = self._parse_utc(fixture_utc_date)
        finished = sorted(
            [
            match
            for match in self._get_finished_matches()
            if self._parse_utc(match["utcDate"]) < fixture_dt
            and {match["homeTeam"]["id"], match["awayTeam"]["id"]} == {home_team_id, away_team_id}
            ],
            key=lambda match: match["utcDate"],
            reverse=True,
        )
        recent = finished[:3]
        home_points = 0
        away_points = 0
        home_goal_diff = 0

        for match in recent:
            home_is_home = match["homeTeam"]["id"] == home_team_id
            home_score = match["score"]["fullTime"]["home"] if home_is_home else match["score"]["fullTime"]["away"]
            away_score = match["score"]["fullTime"]["away"] if home_is_home else match["score"]["fullTime"]["home"]
            if home_score > away_score:
                home_points += 3
            elif home_score < away_score:
                away_points += 3
            else:
                home_points += 1
                away_points += 1
            home_goal_diff += home_score - away_score

        return HeadToHeadSummary(
            home_team=home_team,
            away_team=away_team,
            home_points_last_3=home_points,
            away_points_last_3=away_points,
            home_goal_diff_last_3=home_goal_diff,
            sample_size=len(recent),
        )

    def _resolve_team(self, team_name: str) -> dict[str, Any]:
        teams = self._get_teams()
        normalized = self._normalize_team_name(team_name)
        canonical = self.TEAM_ALIASES.get(normalized, normalized)

        if canonical in teams:
            return teams[canonical]

        partial_matches = [team for key, team in teams.items() if canonical in key or key in canonical]
        if len(partial_matches) == 1:
            return partial_matches[0]

        raise LiveDataProviderError(f"Could not resolve EPL team name: {team_name}")

    def _get_teams(self) -> dict[str, dict[str, Any]]:
        if self._teams_cache is None:
            response = self._request_json(
                f"/competitions/{self.COMPETITION_CODE}/teams",
                params={"season": str(self.SEASON_START_YEAR)},
            )
            teams: dict[str, dict[str, Any]] = {}
            for team in response.get("teams", []):
                variants = {
                    self._normalize_team_name(team["name"]),
                    self._normalize_team_name(team.get("shortName", "")),
                    self._normalize_team_name(team.get("tla", "")),
                }
                for variant in variants:
                    if variant:
                        teams[variant] = team
            self._teams_cache = teams
        return self._teams_cache

    def _get_standings(self) -> dict[int, int]:
        if self._standings_cache is None:
            response = self._request_json(
                f"/competitions/{self.COMPETITION_CODE}/standings",
                params={"season": str(self.SEASON_START_YEAR)},
            )
            standings: dict[int, int] = {}
            for table in response.get("standings", []):
                if table.get("type") != "TOTAL":
                    continue
                for row in table.get("table", []):
                    standings[row["team"]["id"]] = row["position"]
                break
            self._standings_cache = standings
        return self._standings_cache

    def _get_scheduled_matches(self) -> list[dict[str, Any]]:
        if self._scheduled_matches_cache is None:
            response = self._request_json(
                f"/competitions/{self.COMPETITION_CODE}/matches",
                params={"season": str(self.SEASON_START_YEAR), "status": "SCHEDULED"},
            )
            self._scheduled_matches_cache = response.get("matches", [])
        return self._scheduled_matches_cache

    def _get_finished_matches(self) -> list[dict[str, Any]]:
        if self._finished_matches_cache is None:
            response = self._request_json(
                f"/competitions/{self.COMPETITION_CODE}/matches",
                params={"season": str(self.SEASON_START_YEAR), "status": "FINISHED"},
            )
            self._finished_matches_cache = response.get("matches", [])
        return self._finished_matches_cache

    def _request_json(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        query = f"?{urlencode(params)}" if params else ""
        request = Request(
            f"{self.base_url}{path}{query}",
            headers={"X-Auth-Token": self.api_token, "User-Agent": "match-board/1.0"},
        )
        try:
            with urlopen(request, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise LiveDataProviderError(f"football-data request failed for {path}: {exc}") from exc

    def _find_next_fixture(
        self, scheduled_matches: list[dict[str, Any]], home_team_id: int, away_team_id: int
    ) -> dict[str, Any] | None:
        candidates = [
            match
            for match in scheduled_matches
            if match["homeTeam"]["id"] == home_team_id and match["awayTeam"]["id"] == away_team_id
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda match: match["utcDate"])
        return candidates[0]

    @staticmethod
    def _normalize_team_name(name: str) -> str:
        normalized = name.lower().replace(".", "").replace("&", "and")
        for token in [" fc", " afc", " cfc"]:
            normalized = normalized.replace(token, "")
        return " ".join(normalized.split())

    @staticmethod
    def _parse_utc(value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)

    @staticmethod
    def _summarize_recent_matches(matches: list[dict[str, Any]], team_id: int) -> dict[str, int]:
        wins = draws = losses = goals_for = goals_against = 0
        for match in matches:
            is_home = match["homeTeam"]["id"] == team_id
            team_goals = match["score"]["fullTime"]["home"] if is_home else match["score"]["fullTime"]["away"]
            opponent_goals = match["score"]["fullTime"]["away"] if is_home else match["score"]["fullTime"]["home"]
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
