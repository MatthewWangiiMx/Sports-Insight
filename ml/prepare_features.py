"""Turn raw games data into a model-ready, leakage-free feature table.

Reads data/raw/games_*.parquet, builds pre-game team-level features (rolling
win %, point differential, rest days) computed only from games strictly
before the game being predicted, and writes a time-based train/val/test
split plus a feature schema to data/processed/.

Usage (from ml/, with .venv active):
    python prepare_features.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from team_form import MIN_PRIOR_GAMES, ROLLING_WINDOWS, add_pregame_features, to_team_game_long

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = REPO_ROOT / "data" / "raw"
DATA_PROCESSED = REPO_ROOT / "data" / "processed"

TRAIN_SEASONS = list(range(2016, 2024))  # 2016-2023
VAL_SEASONS = [2024]
TEST_SEASONS = [2025]


def load_games() -> pd.DataFrame:
    frames = [pd.read_parquet(f) for f in sorted(DATA_RAW.glob("games_*.parquet"))]
    games = pd.concat(frames, ignore_index=True)
    games["date"] = pd.to_datetime(games["date"])
    games = games.sort_values("date").reset_index(drop=True)
    return games


def build_game_features(games: pd.DataFrame, team_features: pd.DataFrame) -> pd.DataFrame:
    """Join the two teams' pre-game features back onto one row per game."""
    feature_cols = [
        "game_id",
        "team_id",
        "games_played_season",
        "rest_days",
        "is_back_to_back",
        "win_pct_season",
        *[f"win_pct_last{w}" for w in ROLLING_WINDOWS],
        *[f"point_diff_last{w}" for w in ROLLING_WINDOWS],
    ]
    tf = team_features[feature_cols]

    home = tf.add_prefix("home_").rename(columns={"home_game_id": "game_id", "home_team_id": "home_team_id"})
    away = tf.add_prefix("away_").rename(columns={"away_game_id": "game_id", "away_team_id": "away_team_id"})

    base = games[
        ["id", "date", "season", "postseason", "home_team_id", "visitor_team_id", "home_team_score", "visitor_team_score"]
    ].rename(columns={"id": "game_id", "visitor_team_id": "away_team_id"})
    base["home_win"] = (base["home_team_score"] > base["visitor_team_score"]).astype(int)

    df = base.merge(home, on=["game_id", "home_team_id"], how="left")
    df = df.merge(away, on=["game_id", "away_team_id"], how="left")

    # Relative ("diff") features: often more useful to a linear model than the raw pair.
    for window in ROLLING_WINDOWS:
        df[f"win_pct_last{window}_diff"] = df[f"home_win_pct_last{window}"] - df[f"away_win_pct_last{window}"]
        df[f"point_diff_last{window}_diff"] = df[f"home_point_diff_last{window}"] - df[f"away_point_diff_last{window}"]
    df["win_pct_season_diff"] = df["home_win_pct_season"] - df["away_win_pct_season"]
    df["rest_days_diff"] = df["home_rest_days"] - df["away_rest_days"]

    return df


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
    df = df[df["split"] != "unused"].reset_index(drop=True)
    return df


def main() -> None:
    games = load_games()
    long_df = to_team_game_long(games)
    long_df = add_pregame_features(long_df)
    df = build_game_features(games, long_df)
    df = split_and_clean(df)

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    out_path = DATA_PROCESSED / "features.parquet"
    df.to_parquet(out_path, index=False)

    # Explicit allowlist rather than "everything except metadata" - keeps outcome-only
    # columns like the final score, or non-ordinal ids, from silently leaking in as features.
    non_feature_cols = {
        "game_id",
        "date",
        "season",
        "home_win",
        "split",
        "home_team_id",
        "away_team_id",
        "home_team_score",
        "visitor_team_score",
        # near-duplicate "day of season" counters (r=0.998 between home/away) - used only
        # as the MIN_PRIOR_GAMES sample-size gate above, not as a model feature.
        "home_games_played_season",
        "away_games_played_season",
    }
    feature_cols = [c for c in df.columns if c not in non_feature_cols]
    schema = {
        "target": "home_win",
        "features": feature_cols,
        "split_column": "split",
        "min_prior_games": MIN_PRIOR_GAMES,
        "rolling_windows": ROLLING_WINDOWS,
        "train_seasons": TRAIN_SEASONS,
        "val_seasons": VAL_SEASONS,
        "test_seasons": TEST_SEASONS,
    }
    with open(DATA_PROCESSED / "feature_schema.json", "w") as f:
        json.dump(schema, f, indent=2)

    print(f"wrote {len(df)} rows -> {out_path.relative_to(REPO_ROOT)}")
    print(df["split"].value_counts())
    print(f"home win rate: {df['home_win'].mean():.3f}")


if __name__ == "__main__":
    main()
