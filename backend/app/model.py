"""Loads the trained win-probability model and scores hypothetical matchups.

Feature computation for a live matchup reuses ml/team_form.team_form_as_of -
the same function used (via add_pregame_features) to build the training
table - so serving can't silently drift from what the model was trained on.
"""

from __future__ import annotations

import re
import sys

import joblib
import pandas as pd

from .data import ML_DIR, REPO_ROOT, team_games

if str(ML_DIR) not in sys.path:
    sys.path.insert(0, str(ML_DIR))

from ratings import elo_win_probability  # noqa: E402
from team_form import MIN_PRIOR_GAMES, add_matchup_features, elo_as_of, resolve_season, team_form_as_of  # noqa: E402

MODEL_VERSION = "winprob_v3"
# Reported instead of MODEL_VERSION when the early-season Elo fallback is used.
ELO_FALLBACK_VERSION = "elo_early_season"
MODEL_PATH = ML_DIR / "models" / f"{MODEL_VERSION}.pkl"

TOP_FACTOR_COUNT = 5

# Plain-English names for the rolling-stat prefixes in team_form.FORM_STATS, used
# to label the "what's driving this prediction" breakdown.
STAT_LABELS = {
    "win_pct": "Win rate",
    "point_diff": "Scoring margin",
    "off_rtg": "Offensive rating",
    "def_rtg": "Defensive rating",
    "efg": "Shooting efficiency",
    "opp_efg": "Opponent shooting allowed",
    "tov_pct": "Turnover rate",
    "oreb_pct": "Offensive rebounding",
    "ft_rate": "Free throw rate",
}

FIXED_LABELS = {
    "rest_days_diff": "Rest advantage",
    "win_pct_season_diff": "Season win rate edge",
    "elo_diff": "Elo rating edge",
    "roster_strength_diff": "Roster strength edge",
}

# Yes/no features need the label to reflect the actual value: a contribution is
# relative to an average game, so "not on a back-to-back" can matter too.
BINARY_LABELS = {
    "postseason": ("Regular-season game", "Postseason game"),
    "home_is_back_to_back": ("Home team rested (no back-to-back)", "Home team on a back-to-back"),
    "away_is_back_to_back": ("Away team rested (no back-to-back)", "Away team on a back-to-back"),
}


def feature_label(name: str, value: float) -> str:
    if name in BINARY_LABELS:
        return BINARY_LABELS[name][int(value)]
    if name in FIXED_LABELS:
        return FIXED_LABELS[name]
    match = re.fullmatch(r"(\w+)_last(\d+)_diff", name)
    if match and match.group(1) in STAT_LABELS:
        return f"{STAT_LABELS[match.group(1)]} edge (last {match.group(2)} games)"
    return name


class ModelNotTrainedError(RuntimeError):
    pass


class InsufficientHistoryError(ValueError):
    def __init__(self, team_id: int, season: int):
        self.team_id = team_id
        self.season = season
        super().__init__(f"team {team_id} has too few games played in season {season} to predict from")


def _load_bundle() -> dict:
    if not MODEL_PATH.exists():
        raise ModelNotTrainedError(f"no model found at {MODEL_PATH.relative_to(REPO_ROOT)}; run ml/train.py first")
    return joblib.load(MODEL_PATH)


try:
    _BUNDLE = _load_bundle()
except ModelNotTrainedError:
    _BUNDLE = None


def _team_features(team_id: int, as_of: pd.Timestamp) -> dict:
    form = team_form_as_of(team_games(team_id), as_of)
    if form is None:
        raise InsufficientHistoryError(team_id, resolve_season(team_games(team_id), as_of))
    return form


def predict_home_win_probability(
    home_team_id: int,
    away_team_id: int,
    as_of: pd.Timestamp,
    postseason: bool = False,
) -> dict:
    try:
        home = _team_features(home_team_id, as_of)
        away = _team_features(away_team_id, as_of)
    except InsufficientHistoryError:
        # Start of a season: the model's form features (last 5/10 games, season
        # win %) need a few games this season, but Elo carries over from last season.
        return _elo_estimate(home_team_id, away_team_id, as_of)

    if _BUNDLE is None:
        raise ModelNotTrainedError(f"no model found at {MODEL_PATH.relative_to(REPO_ROOT)}; run ml/train.py first")

    row = {"postseason": int(postseason)}
    for key, value in home.items():
        row[f"home_{key}"] = value
    for key, value in away.items():
        row[f"away_{key}"] = value
    add_matchup_features(row)

    features: list[str] = _BUNDLE["features"]
    X = pd.DataFrame([row])[features]
    pipeline = _BUNDLE["model"]
    home_win_probability = float(pipeline.predict_proba(X)[0, 1])

    factors = _explain(pipeline, X, features, home_win_probability)

    return {
        "home_win_probability": home_win_probability,
        "away_win_probability": 1.0 - home_win_probability,
        "season": resolve_season(team_games(home_team_id), as_of),
        "home_form": home,
        "away_form": away,
        "model_version": MODEL_VERSION,
        "factors": factors,
        "note": None,
    }


def _elo_estimate(home_team_id: int, away_team_id: int, as_of: pd.Timestamp) -> dict:
    """Win probability from Elo alone - the fallback until both teams have
    MIN_PRIOR_GAMES games this season. Less informed than the model (no recent
    form, rest or roster), but Elo was the model's strongest single feature."""
    home_games, away_games = team_games(home_team_id), team_games(away_team_id)
    home_elo, away_elo = elo_as_of(home_games, as_of), elo_as_of(away_games, as_of)
    season = resolve_season(home_games, as_of)
    if home_elo is None:
        raise InsufficientHistoryError(home_team_id, season)
    if away_elo is None:
        raise InsufficientHistoryError(away_team_id, season)

    p = elo_win_probability(home_elo, away_elo)
    # Split the edge into its two parts: home court alone (equal ratings), and
    # what the rating gap adds or takes away on top of that.
    p_home_court = elo_win_probability(home_elo, home_elo)
    factors = [
        {"label": "Elo rating edge", "favors": "home" if home_elo >= away_elo else "away", "impact_pct": abs(p - p_home_court) * 100},
        {"label": "Home court advantage", "favors": "home", "impact_pct": (p_home_court - 0.5) * 100},
    ]
    return {
        "home_win_probability": p,
        "away_win_probability": 1.0 - p,
        "season": season,
        "model_version": ELO_FALLBACK_VERSION,
        "factors": sorted(factors, key=lambda f: f["impact_pct"], reverse=True),
        "note": (
            f"Early-season estimate: the full model needs {MIN_PRIOR_GAMES} games from each team this season, "
            "so this uses Elo ratings alone (carried over from last season, updated after every game)."
        ),
    }


def _explain(pipeline, X: pd.DataFrame, features: list[str], home_win_probability: float) -> list[dict]:
    """Top contributing factors behind one prediction, derived from the logistic
    regression's own coefficients - not SHAP, just the model's actual linear math.

    predict_proba = sigmoid(sum(coef_i * scaled_feature_i) + intercept), so each
    feature's logit contribution is coef_i * scaled_feature_i. Converting that to an
    approximate probability-point impact uses the *local* derivative of the sigmoid at
    this prediction's own probability (p * (1 - p)), rather than a fixed constant -
    that derivative shrinks as a prediction gets more confident (e.g. 0.16 at p=0.8 vs
    0.25 at p=0.5), so a flat multiplier would overstate impacts on confident predictions.
    """
    scaler = pipeline.named_steps["scaler"]
    clf = pipeline.named_steps["clf"]
    X_scaled = scaler.transform(X)[0]
    contributions = clf.coef_[0] * X_scaled

    local_slope = home_win_probability * (1.0 - home_win_probability)
    ranked = sorted(zip(features, contributions), key=lambda fc: abs(fc[1]), reverse=True)

    return [
        {
            "label": feature_label(name, X.iloc[0][name]),
            "favors": "home" if contrib > 0 else "away",
            "impact_pct": abs(float(contrib)) * local_slope * 100,
        }
        for name, contrib in ranked[:TOP_FACTOR_COUNT]
    ]
