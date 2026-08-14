from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class TeamOut(BaseModel):
    id: int
    full_name: str
    abbreviation: str
    conference: str
    division: str


class TeamSeasonStats(BaseModel):
    team_id: int
    season: int
    games_played: int
    wins: int
    losses: int
    win_pct: float
    avg_point_diff: float


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
