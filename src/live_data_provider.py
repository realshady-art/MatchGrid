from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class TeamRecentForm:
    team: str
    wins_last_5: int
    draws_last_5: int
    losses_last_5: int
    points_last_5: int
    goals_for_last_5: int
    goals_against_last_5: int
    rest_days: int


@dataclass
class HeadToHeadSummary:
    home_team: str
    away_team: str
    home_points_last_3: int
    away_points_last_3: int
    home_goal_diff_last_3: int


class LiveDataProvider(Protocol):
    def get_team_recent_form(self, team_name: str) -> TeamRecentForm:
        ...

    def get_head_to_head_summary(self, home_team: str, away_team: str) -> HeadToHeadSummary:
        ...


class PlaceholderLiveDataProvider:
    """Stub implementation to be replaced by a real EPL API client."""

    def get_team_recent_form(self, team_name: str) -> TeamRecentForm:
        raise NotImplementedError(
            f"No live API provider configured for team form lookup: {team_name}"
        )

    def get_head_to_head_summary(self, home_team: str, away_team: str) -> HeadToHeadSummary:
        raise NotImplementedError(
            f"No live API provider configured for head-to-head lookup: {home_team} vs {away_team}"
        )
