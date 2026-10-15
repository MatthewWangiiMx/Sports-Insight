"""Pre-game team feature logic shared by training and serving.

ml/prepare_features.py uses this to build the historical, leakage-checked
training table (shift(1) before every rolling stat). The backend imports it
too, to compute a live "current form" snapshot for a hypothetical matchup -
using the same functions in both places means the API can never silently
drift from what the model was actually trained on.

Input is the team-centric long table from nba_source.load_team_games.
"""

from __future__ import annotations

import pandas as pd

# Rolling window sizes (in games) used for "recent form" features.
ROLLING_WINDOWS = [5, 10]
# A team needs at least this many prior games *in the season* before its
# rolling/season features are considered reliable enough to use.
MIN_PRIOR_GAMES = 3
# In-season rest is almost always 1-4 days; beyond a week more rest doesn't
# matter. Capping also keeps off-season predictions (weeks/months since a team's
# last game) from extrapolating far outside anything the model trained on.
REST_DAYS_CAP = 7

# Per-game stat column (from nba_source) -> feature name prefix. Every entry
# becomes a rolling "<prefix>_last<N>" feature for each window. net_rtg is left
# out on purpose: it's exactly off_rtg - def_rtg, so including all three would
# give the model a perfectly redundant feature.
FORM_STATS = {
    "win": "win_pct",
    "point_diff": "point_diff",
    "off_rtg": "off_rtg",
    "def_rtg": "def_rtg",
    "efg": "efg",
    "opp_efg": "opp_efg",
    "tov_pct": "tov_pct",
    "oreb_pct": "oreb_pct",
    "ft_rate": "ft_rate",
}

ROLLING_FEATURES = [f"{prefix}_last{w}" for prefix in FORM_STATS.values() for w in ROLLING_WINDOWS]

# Per-team pre-game features computed for each side of a matchup.
TEAM_FEATURES = ["rest_days", "is_back_to_back", "win_pct_season", *ROLLING_FEATURES]

# Which rolling stats the model actually uses. The ratings / Four Factors are
# still computed (for display), but in a linear model they added no accuracy
# over win% + margin - margin is largely their outcome - and their overlap with
# margin produced backwards-signed coefficients (e.g. better offense -> lower
# win chance), which would make the prediction explanations misleading.
MODEL_STAT_PREFIXES = ["win_pct", "point_diff"]

# Features that enter the model as a home-minus-away difference. Only the diff
# is used (not the home and away values too): diff = home - away exactly, so
# keeping all three would make the coefficients arbitrary.
DIFF_FEATURES = [
    "rest_days",
    "win_pct_season",
    *[f"{p}_last{w}" for p in MODEL_STAT_PREFIXES for w in ROLLING_WINDOWS],
]

MODEL_FEATURES = [
    "postseason",
    # Back-to-backs stay per-side: a tired home team and a tired away team
    # aren't symmetric effects, and a 0/1 diff would hide "both tired".
    "home_is_back_to_back",
    "away_is_back_to_back",
    *[f"{f}_diff" for f in DIFF_FEATURES],
]


def season_for_date(date: pd.Timestamp) -> int:
    """NBA seasons are labeled by their starting year (e.g. "2023" = 2023-24).
    Regular season/playoffs run roughly Oct-June; treat Aug/Sep as the start
    of the *next* season (preseason).
    """
    return date.year if date.month >= 8 else date.year - 1


def add_pregame_features(long_df: pd.DataFrame) -> pd.DataFrame:
    """Add rolling/expanding stats computed strictly from *prior* games (shift(1)).

    Used to build the historical training table: for a game already in the
    dataset, this excludes that game's own result from its own features.
    """
    g = long_df.groupby("team_id")

    # Rest days since the team's previous game (any season). First game ever -> NaN.
    prev_date = g["date"].shift(1)
    long_df["rest_days"] = (long_df["date"] - prev_date).dt.days.clip(upper=REST_DAYS_CAP)
    long_df["is_back_to_back"] = (long_df["rest_days"] <= 1).astype("Int64")

    # Season-scoped rolling/expanding stats: reset each season since rosters change.
    season_g = long_df.groupby(["team_id", "season"])
    long_df["games_played_season"] = season_g.cumcount()
    long_df["win_pct_season"] = season_g["win"].transform(lambda s: s.shift(1).expanding().mean())

    for stat, prefix in FORM_STATS.items():
        for window in ROLLING_WINDOWS:
            long_df[f"{prefix}_last{window}"] = season_g[stat].transform(
                lambda s, w=window: s.shift(1).rolling(w, min_periods=1).mean()
            )

    return long_df


def add_matchup_features(row):
    """Home-minus-away diffs for one matchup. Works on a DataFrame (training,
    one row per game) or a plain dict (serving, one hypothetical game), since
    both support row["col"] access and arithmetic.
    """
    for f in DIFF_FEATURES:
        row[f"{f}_diff"] = row[f"home_{f}"] - row[f"away_{f}"]
    return row


def team_form_as_of(team_games: pd.DataFrame, as_of: pd.Timestamp, min_prior_games: int = MIN_PRIOR_GAMES) -> dict | None:
    """Pre-game feature snapshot for one team entering a new game on `as_of`.

    `team_games` must be that single team's rows from the long table. Unlike
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
    rest_days = min(int((as_of - prior_games["date"].iloc[-1]).days), REST_DAYS_CAP)

    features = {
        "games_played_season": int(len(season_games)),
        "rest_days": rest_days,
        "is_back_to_back": int(rest_days <= 1),
        "win_pct_season": float(season_games["win"].mean()),
    }
    for stat, prefix in FORM_STATS.items():
        for window in ROLLING_WINDOWS:
            features[f"{prefix}_last{window}"] = float(season_games[stat].tail(window).mean())
    return features
