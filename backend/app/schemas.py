from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class TeamOut(BaseModel):
    id: int
    full_name: str
    abbreviation: str
    conference: str
    division: str


class GameLogEntry(BaseModel):
    date: date
    opponent_abbreviation: str
    is_home: bool
    win: bool
    point_diff: int


class TeamSeasonStats(BaseModel):
    team_id: int
    season: int
    games_played: int
    wins: int
    losses: int
    win_pct: float
    avg_point_diff: float
    home_wins: int
    home_losses: int
    away_wins: int
    away_losses: int
    current_streak: str
    game_log: list[GameLogEntry]


class StandingsRow(BaseModel):
    team: TeamOut
    season: int
    wins: int
    losses: int
    win_pct: float
    conference_rank: int
    division_rank: int
    games_behind: float


class HeadToHead(BaseModel):
    team_a: TeamOut
    team_b: TeamOut
    team_a_wins: int
    team_b_wins: int
    games_played: int
    last_meeting_date: date | None
    last_meeting_winner_id: int | None


class PredictionFactor(BaseModel):
    label: str
    favors: Literal["home", "away"]
    impact_pct: float


class PredictRequest(BaseModel):
    home_team_id: int
    away_team_id: int
    game_date: date | None = Field(default=None, description="Defaults to the day after our latest ingested game.")
    postseason: bool = False


class PredictResponse(BaseModel):
    home_team: TeamOut
    away_team: TeamOut
    home_win_probability: float
    away_win_probability: float
    as_of_date: date
    season: int
    model_version: str
    factors: list[PredictionFactor]
