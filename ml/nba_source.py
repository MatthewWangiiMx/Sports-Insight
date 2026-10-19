"""Loads the stats.nba.com team game logs (data/raw/nba/) into the team-centric
"long" table every downstream step works from: one row per (team, game), with
the opponent's box score joined on and per-game advanced stats derived.

Shared by ml/prepare_features.py and the backend, same as team_form.py.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

BOX_COLS = ["pts", "fgm", "fga", "fg3m", "ftm", "fta", "oreb", "dreb", "reb", "ast", "stl", "blk", "tov", "pf"]


def load_teams(raw_dir: Path) -> pd.DataFrame:
    return pd.read_parquet(raw_dir / "teams.parquet").sort_values("full_name").reset_index(drop=True)


def load_team_games(raw_dir: Path) -> pd.DataFrame:
    frames = [pd.read_parquet(f) for f in sorted(raw_dir.glob("team_games_*.parquet"))]
    df = pd.concat(frames, ignore_index=True).rename(columns=str.lower)

    opp = df[["game_id", "team_id", *BOX_COLS]].rename(
        columns={"team_id": "opponent_id", **{c: f"opp_{c}" for c in BOX_COLS}}
    )
    long_df = df.merge(opp, on="game_id")
    long_df = long_df[long_df["team_id"] != long_df["opponent_id"]].copy()

    long_df = long_df.rename(columns={"game_date": "date", "pts": "team_score", "opp_pts": "opp_score"})
    long_df["win"] = (long_df["wl"] == "W").astype(int)
    long_df["point_diff"] = long_df["team_score"] - long_df["opp_score"]
    _add_advanced_stats(long_df)

    return long_df.sort_values(["team_id", "date"]).reset_index(drop=True)


def load_player_games(raw_dir: Path) -> pd.DataFrame:
    """Player game logs for players who actually got on the court, with a
    per-game Hollinger Game Score - a one-number box-score summary of a game."""
    frames = [pd.read_parquet(f) for f in sorted(raw_dir.glob("player_games_*.parquet"))]
    pg = pd.concat(frames, ignore_index=True).rename(columns=str.lower).rename(columns={"game_date": "date"})
    pg = pg[pg["min"] > 0].copy()
    pg["game_score"] = (
        pg["pts"] + 0.4 * pg["fgm"] - 0.7 * pg["fga"] - 0.4 * (pg["fta"] - pg["ftm"])
        + 0.7 * pg["oreb"] + 0.3 * pg["dreb"] + pg["stl"] + 0.7 * pg["ast"] + 0.7 * pg["blk"]
        - 0.4 * pg["pf"] - pg["tov"]
    )
    return pg.sort_values(["player_id", "date"]).reset_index(drop=True)


def _add_advanced_stats(df: pd.DataFrame) -> None:
    # Possessions: the common box-score estimate, averaged over both teams since
    # each team's own estimate is noisy but they played (nearly) the same number.
    team_poss = df["fga"] - df["oreb"] + df["tov"] + 0.44 * df["fta"]
    opp_poss = df["opp_fga"] - df["opp_oreb"] + df["opp_tov"] + 0.44 * df["opp_fta"]
    df["possessions"] = (team_poss + opp_poss) / 2

    # Points per 100 possessions - pace-adjusted, unlike raw points or margin.
    df["off_rtg"] = 100 * df["team_score"] / df["possessions"]
    df["def_rtg"] = 100 * df["opp_score"] / df["possessions"]
    df["net_rtg"] = df["off_rtg"] - df["def_rtg"]

    # Dean Oliver's "Four Factors" (shooting, turnovers, rebounding, free throws),
    # plus the opponent's shooting as the main defensive one.
    df["efg"] = (df["fgm"] + 0.5 * df["fg3m"]) / df["fga"]
    df["opp_efg"] = (df["opp_fgm"] + 0.5 * df["opp_fg3m"]) / df["opp_fga"]
    df["tov_pct"] = df["tov"] / (df["fga"] + 0.44 * df["fta"] + df["tov"])
    df["oreb_pct"] = df["oreb"] / (df["oreb"] + df["opp_dreb"])
    df["ft_rate"] = df["ftm"] / df["fga"]
