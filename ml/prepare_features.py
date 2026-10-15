"""Turn raw stats.nba.com game logs into a model-ready, leakage-free feature table.

Reads data/raw/nba/team_games_*.parquet, builds pre-game team-level features
(rolling win %, margin, offensive/defensive rating, Four Factors, rest days)
computed only from games strictly before the game being predicted, and writes
a time-based train/val/test split plus a feature schema to data/processed/.

Usage (from ml/, with .venv active):
    python prepare_features.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from nba_source import load_team_games
from team_form import (
    MIN_PRIOR_GAMES,
    MODEL_FEATURES,
    ROLLING_WINDOWS,
    TEAM_FEATURES,
    add_matchup_features,
    add_pregame_features,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_RAW_NBA = REPO_ROOT / "data" / "raw" / "nba"
DATA_PROCESSED = REPO_ROOT / "data" / "processed"

TRAIN_SEASONS = list(range(2016, 2024))  # 2016-2023
VAL_SEASONS = [2024]
TEST_SEASONS = [2025]


def build_game_features(long_df: pd.DataFrame) -> pd.DataFrame:
    """One row per game (home vs away) with both teams' pre-game features."""
    # Neutral-site games have no home team, and the model predicts "home team
    # wins" - they still feed each team's rolling form, but aren't rows here.
    home_rows = long_df[long_df["is_home"] & ~long_df["neutral_site"]]
    games = home_rows[["game_id", "date", "season", "postseason", "team_id", "opponent_id", "team_score", "opp_score"]].rename(
        columns={"team_id": "home_team_id", "opponent_id": "away_team_id", "team_score": "home_score", "opp_score": "away_score"}
    )
    games["home_win"] = (games["home_score"] > games["away_score"]).astype(int)

    tf = long_df[["game_id", "team_id", "games_played_season", *TEAM_FEATURES]]
    home = tf.add_prefix("home_").rename(columns={"home_game_id": "game_id"})
    away = tf.add_prefix("away_").rename(columns={"away_game_id": "game_id"})

    df = games.merge(home, on=["game_id", "home_team_id"]).merge(away, on=["game_id", "away_team_id"])
    return add_matchup_features(df)


def split_and_clean(df: pd.DataFrame) -> pd.DataFrame:
    # Require both teams to have a minimum sample of prior games this season,
    # so rolling stats aren't computed on 0-1 games of noise.
    enough_history = (df["home_games_played_season"] >= MIN_PRIOR_GAMES) & (
        df["away_games_played_season"] >= MIN_PRIOR_GAMES
    )
    df = df[enough_history].copy()

    def assign_split(season: int) -> str:
        if season in TRAIN_SEASONS:
            return "train"
        if season in VAL_SEASONS:
            return "val"
        if season in TEST_SEASONS:
            return "test"
        return "unused"

    df["split"] = df["season"].apply(assign_split)
    return df[df["split"] != "unused"].sort_values("date").reset_index(drop=True)


def main() -> None:
    long_df = add_pregame_features(load_team_games(DATA_RAW_NBA))
    df = split_and_clean(build_game_features(long_df))

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    out_path = DATA_PROCESSED / "features.parquet"
    df.to_parquet(out_path, index=False)

    schema = {
        "target": "home_win",
        "features": MODEL_FEATURES,
        "split_column": "split",
        "min_prior_games": MIN_PRIOR_GAMES,
        "rolling_windows": ROLLING_WINDOWS,
        "train_seasons": TRAIN_SEASONS,
        "val_seasons": VAL_SEASONS,
        "test_seasons": TEST_SEASONS,
    }
    with open(DATA_PROCESSED / "feature_schema.json", "w") as f:
        json.dump(schema, f, indent=2)

    print(f"wrote {len(df)} rows, {len(MODEL_FEATURES)} features -> {out_path.relative_to(REPO_ROOT)}")
    print(df["split"].value_counts())
    print(f"home win rate: {df['home_win'].mean():.3f}")
    print(f"null feature values: {int(df[MODEL_FEATURES].isna().sum().sum())}")


if __name__ == "__main__":
    main()
