import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import data, players
from .model import InsufficientHistoryError, ModelNotTrainedError, predict_home_win_probability
from .schemas import (
    HeadToHead,
    LeaderEntry,
    PlayerStats,
    PlayerSummary,
    PredictRequest,
    PredictResponse,
    RosterEntry,
    StandingsRow,
    TeamOut,
    TeamSeasonStats,
)

app = FastAPI(title="Sports Insight API")

app.add_middleware(
    CORSMiddleware,
    # Matches any localhost dev port, not just Vite's default 5173 - Vite silently
    # bumps to 5174+ when 5173 is already taken, which otherwise breaks every
    # frontend request with an opaque CORS rejection rather than a clear error.
    allow_origin_regex=r"http://localhost:\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/teams", response_model=list[TeamOut])
def list_teams() -> list[dict]:
    return data.list_teams()


@app.get("/teams/{team_id}", response_model=TeamOut)
def get_team(team_id: int) -> dict:
    team = data.get_team(team_id)
    if team is None:
        raise HTTPException(status_code=404, detail=f"no team with id {team_id}")
    return team


@app.get("/teams/{team_id}/stats", response_model=TeamSeasonStats)
def team_season_stats(team_id: int, season: int | None = None) -> dict:
    if data.get_team(team_id) is None:
        raise HTTPException(status_code=404, detail=f"no team with id {team_id}")

    season = season if season is not None else data.LATEST_SEASON
    stats = data.team_season_stats(team_id, season)
    if stats is None:
        raise HTTPException(status_code=404, detail=f"no games found for team {team_id} in season {season}")
    return stats


@app.get("/standings", response_model=list[StandingsRow])
def standings(season: int | None = None) -> list[dict]:
    season = season if season is not None else data.LATEST_SEASON
    rows = data.season_standings(season)
    if not rows:
        raise HTTPException(status_code=404, detail=f"no games found for season {season}")
    return rows


@app.get("/teams/{team_a_id}/vs/{team_b_id}", response_model=HeadToHead)
def head_to_head(team_a_id: int, team_b_id: int) -> dict:
    team_a = data.get_team(team_a_id)
    team_b = data.get_team(team_b_id)
    if team_a is None:
        raise HTTPException(status_code=404, detail=f"no team with id {team_a_id}")
    if team_b is None:
        raise HTTPException(status_code=404, detail=f"no team with id {team_b_id}")
    return {"team_a": team_a, "team_b": team_b, **data.head_to_head(team_a_id, team_b_id)}


@app.get("/teams/{team_id}/roster", response_model=list[RosterEntry])
def team_roster(team_id: int, season: int | None = None) -> list[dict]:
    if data.get_team(team_id) is None:
        raise HTTPException(status_code=404, detail=f"no team with id {team_id}")
    return players.team_roster(team_id, season if season is not None else data.LATEST_SEASON)


@app.get("/players", response_model=list[PlayerSummary])
def list_players() -> list[dict]:
    return players.list_players()


@app.get("/players/{player_id}/stats", response_model=PlayerStats)
def player_stats(player_id: int, season: int | None = None) -> dict:
    stats = players.player_stats(player_id, season)
    if stats is None:
        detail = f"no regular-season games for player {player_id}" + (f" in season {season}" if season else "")
        raise HTTPException(status_code=404, detail=detail)
    return stats


@app.get("/leaders", response_model=list[LeaderEntry])
def leaders(stat: str = "pts", season: int | None = None, limit: int = 10) -> list[dict]:
    if stat not in players.LEADER_STATS:
        raise HTTPException(status_code=400, detail=f"stat must be one of: {', '.join(players.LEADER_STATS)}")
    return players.leaders(season if season is not None else data.LATEST_SEASON, stat, max(1, min(limit, 50)))


@app.post("/predict/winprob", response_model=PredictResponse)
def predict_winprob(req: PredictRequest) -> dict:
    if req.home_team_id == req.away_team_id:
        raise HTTPException(status_code=400, detail="home_team_id and away_team_id must differ")

    home_team = data.get_team(req.home_team_id)
    away_team = data.get_team(req.away_team_id)
    if home_team is None:
        raise HTTPException(status_code=404, detail=f"no team with id {req.home_team_id}")
    if away_team is None:
        raise HTTPException(status_code=404, detail=f"no team with id {req.away_team_id}")

    as_of = pd.Timestamp(req.game_date) if req.game_date else data.default_as_of()

    try:
        result = predict_home_win_probability(req.home_team_id, req.away_team_id, as_of, req.postseason)
    except InsufficientHistoryError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"team {exc.team_id} has fewer than the required prior games in season {exc.season} "
            "as of this date - pick a later date or a season with more games played",
        ) from exc
    except ModelNotTrainedError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "home_team": home_team,
        "away_team": away_team,
        "home_win_probability": result["home_win_probability"],
        "away_win_probability": result["away_win_probability"],
        "as_of_date": as_of.date(),
        "season": result["season"],
        "model_version": result["model_version"],
        "factors": result["factors"],
    }
