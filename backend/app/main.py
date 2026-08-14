import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import data
from .model import InsufficientHistoryError, ModelNotTrainedError, predict_home_win_probability
from .schemas import PredictRequest, PredictResponse, TeamOut, TeamSeasonStats

app = FastAPI(title="Sports Insight API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
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

    season = season if season is not None else int(data.GAMES["season"].max())
    games = data.team_games(team_id)
    games = games[games["season"] == season]
    if games.empty:
        raise HTTPException(status_code=404, detail=f"no games found for team {team_id} in season {season}")

    wins = int(games["win"].sum())
    return {
        "team_id": team_id,
        "season": season,
        "games_played": int(len(games)),
        "wins": wins,
        "losses": int(len(games)) - wins,
        "win_pct": float(games["win"].mean()),
        "avg_point_diff": float(games["point_diff"].mean()),
    }


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
    }
