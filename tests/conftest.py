"""Shared test setup. Runs before any test module is imported, so the backend
(which loads data at import time) sees the generated league, never real data
or the Supabase database."""

from __future__ import annotations

import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
# ml/ for the shared modules, backend/ for `app`, tests/ for `synthetic`.
sys.path[:0] = [str(REPO_ROOT / "ml"), str(REPO_ROOT / "backend"), str(REPO_ROOT / "tests")]

from synthetic import write_league  # noqa: E402

RAW_DIR = Path(tempfile.mkdtemp(prefix="sports-insight-league-"))
write_league(RAW_DIR)
atexit.register(shutil.rmtree, RAW_DIR, ignore_errors=True)

os.environ["NBA_RAW_DIR"] = str(RAW_DIR)
# Force parquet even if backend/.env has a DATABASE_URL.
os.environ["DATA_SOURCE"] = "parquet"


@pytest.fixture(scope="session")
def raw_dir() -> Path:
    return RAW_DIR


@pytest.fixture(scope="session")
def long_df(raw_dir):
    """Team-centric long table with ratings - what training and the API both start from."""
    from nba_source import load_player_games, load_team_games
    from ratings import add_ratings

    return add_ratings(load_team_games(raw_dir), load_player_games(raw_dir))


@pytest.fixture(scope="session")
def pregame(long_df):
    from team_form import add_pregame_features

    return add_pregame_features(long_df.copy())
