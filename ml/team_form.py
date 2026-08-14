"""Pre-game team feature logic shared by training and serving.

ml/prepare_features.py uses this to build the historical, leakage-checked
training table (shift(1) before every rolling stat). The backend imports it
too, to compute a live "current form" snapshot for a hypothetical matchup -
using the same functions in both places means the API can never silently
drift from what the model was actually trained on.
"""

from __future__ import annotations

import pandas as pd

# Rolling window sizes (in games) used for "recent form" features.
ROLLING_WINDOWS = [5, 10]
# A team needs at least this many prior games *in the season* before its
# rolling/season features are considered reliable enough to use.
MIN_PRIOR_GAMES = 3


def season_for_date(date: pd.Timestamp) -> int:
    """NBA seasons are labeled by their starting year (e.g. "2023" = 2023-24).
    Regular season/playoffs run roughly Oct-June; treat Aug/Sep as the start
    of the *next* season (preseason), matching how balldontlie labels games.
    """
    return date.year if date.month >= 8 else date.year - 1


def to_team_game_long(games: pd.DataFrame) -> pd.DataFrame:
    """One row per (team, game): the team-centric view used to compute rolling stats."""
    home = pd.DataFrame(
        {
            "game_id": games["id"],
            "date": games["date"],
            "season": games["season"],
            "postseason": games["postseason"],
            "team_id": games["home_team_id"],
            "opponent_id": games["visitor_team_id"],
            "is_home": True,
            "team_score": games["home_team_score"],
            "opp_score": games["visitor_team_score"],
        }
    )
    away = pd.DataFrame(
        {
            "game_id": games["id"],
            "date": games["date"],
            "season": games["season"],
            "postseason": games["postseason"],
            "team_id": games["visitor_team_id"],
            "opponent_id": games["home_team_id"],
            "is_home": False,
            "team_score": games["visitor_team_score"],
            "opp_score": games["home_team_score"],
        }
    )
    long_df = pd.concat([home, away], ignore_index=True)
    long_df["win"] = (long_df["team_score"] > long_df["opp_score"]).astype(int)
    long_df["point_diff"] = long_df["team_score"] - long_df["opp_score"]
    long_df = long_df.sort_values(["team_id", "date"]).reset_index(drop=True)
    return long_df


def add_pregame_features(long_df: pd.DataFrame) -> pd.DataFrame:
    """Add rolling/expanding stats computed strictly from *prior* games (shift(1)).

    Used to build the historical training table: for a game already in the
    dataset, this excludes that game's own result from its own features.
    """
    g = long_df.groupby("team_id", group_keys=False)
    long_df["games_played_career"] = g.cumcount()

    # Rest days since the team's previous game (any season). First game ever -> NaN.
    long_df["prev_game_date"] = g["date"].shift(1)
    long_df["rest_days"] = (long_df["date"] - long_df["prev_game_date"]).dt.days
    long_df["is_back_to_back"] = (long_df["rest_days"] <= 1).astype("Int64")

    # Season-scoped rolling/expanding stats: reset each season since rosters change.
    season_g = long_df.groupby(["team_id", "season"], group_keys=False)
    long_df["games_played_season"] = season_g.cumcount()
    long_df["win_pct_season"] = season_g["win"].apply(lambda s: s.shift(1).expanding().mean())

    for window in ROLLING_WINDOWS:
        long_df[f"win_pct_last{window}"] = season_g["win"].apply(
            lambda s, w=window: s.shift(1).rolling(w, min_periods=1).mean()
        )
        long_df[f"point_diff_last{window}"] = season_g["point_diff"].apply(
            lambda s, w=window: s.shift(1).rolling(w, min_periods=1).mean()
        )

    return long_df


def team_form_as_of(team_games: pd.DataFrame, as_of: pd.Timestamp, min_prior_games: int = MIN_PRIOR_GAMES) -> dict | None:
    """Pre-game feature snapshot for one team entering a new game on `as_of`.

    `team_games` must be that single team's rows (any seasons), with columns
    date/season/win/point_diff, as produced by `to_team_game_long`. Unlike
    `add_pregame_features` (which looks *backward* from an existing row via
    shift(1)), this looks forward from the team's real history to a
    not-yet-played date - there's no self-row to exclude, so no shift needed.

    Returns None if the team hasn't played `min_prior_games` games yet in the
    season `as_of` falls into (too little signal to trust).
    """
    season = season_for_date(as_of)
    season_games = team_games[(team_games["season"] == season) & (team_games["date"] < as_of)].sort_values("date")
    if len(season_games) < min_prior_games:
        return None

    prior_games = team_games[team_games["date"] < as_of].sort_values("date")
    rest_days = int((as_of - prior_games["date"].iloc[-1]).days)

    features = {
        "games_played_season": int(len(season_games)),
        "rest_days": rest_days,
        "is_back_to_back": int(rest_days <= 1),
        "win_pct_season": float(season_games["win"].mean()),
    }
    for window in ROLLING_WINDOWS:
        tail = season_games.tail(window)
        features[f"win_pct_last{window}"] = float(tail["win"].mean())
        features[f"point_diff_last{window}"] = float(tail["point_diff"].mean())
    return features
