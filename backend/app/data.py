"""Loads teams/games from data/raw/ once at process start and keeps them in memory.

At our data volume (~13k games) this is simpler and faster than hitting disk
or the upstream API per request, and it *is* the caching layer for now -
refreshing means re-running ml/ingest and restarting the API.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
DATA_RAW = REPO_ROOT / "data" / "raw"

ML_DIR = REPO_ROOT / "ml"
if str(ML_DIR) not in sys.path:
    sys.path.insert(0, str(ML_DIR))

from team_form import to_team_game_long  # noqa: E402


def _load_teams() -> pd.DataFrame:
    df = pd.read_parquet(DATA_RAW / "teams.parquet")
    # Current NBA franchises only (ids 1-30); the rest are defunct 1940s-50s
    # BAA teams the API keeps for historical completeness.
    return df[df["conference"].isin(["East", "West"])].sort_values("full_name").reset_index(drop=True)


def _load_games() -> pd.DataFrame:
    frames = [pd.read_parquet(f) for f in sorted(DATA_RAW.glob("games_*.parquet"))]
    games = pd.concat(frames, ignore_index=True)
    games["date"] = pd.to_datetime(games["date"])
    return games.sort_values("date").reset_index(drop=True)


TEAMS = _load_teams()
GAMES = _load_games()
TEAM_GAMES_LONG = to_team_game_long(GAMES)
LATEST_GAME_DATE: pd.Timestamp = GAMES["date"].max()


def get_team(team_id: int) -> dict | None:
    row = TEAMS[TEAMS["id"] == team_id]
    return None if row.empty else row.iloc[0].to_dict()


def list_teams() -> list[dict]:
    return TEAMS.to_dict(orient="records")


def team_games(team_id: int) -> pd.DataFrame:
    return TEAM_GAMES_LONG[TEAM_GAMES_LONG["team_id"] == team_id]


def default_as_of() -> pd.Timestamp:
    """Day after the most recent game we have data for.

    There's no live feed, so "predict as of right now" only makes sense in
    terms of the data we've actually ingested - this lands on whatever
    season's final games were most recently pulled.
    """
    return LATEST_GAME_DATE + pd.Timedelta(days=1)
