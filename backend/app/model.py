"""Loads the trained win-probability model and scores hypothetical matchups.

Feature computation for a live matchup reuses ml/team_form.team_form_as_of -
the same function used (via add_pregame_features) to build the training
table - so serving can't silently drift from what the model was trained on.
"""

from __future__ import annotations

import sys
from pathlib import Path

import joblib
import pandas as pd

from .data import ML_DIR, REPO_ROOT, team_games

if str(ML_DIR) not in sys.path:
    sys.path.insert(0, str(ML_DIR))

from team_form import season_for_date, team_form_as_of  # noqa: E402

MODEL_PATH = ML_DIR / "models" / "winprob_v1.pkl"


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

MODEL_VERSION = "winprob_v1"


def _team_features(team_id: int, as_of: pd.Timestamp) -> dict:
    form = team_form_as_of(team_games(team_id), as_of)
    if form is None:
        raise InsufficientHistoryError(team_id, season_for_date(as_of))
    return form


def predict_home_win_probability(
    home_team_id: int,
    away_team_id: int,
    as_of: pd.Timestamp,
    postseason: bool = False,
) -> dict:
    if _BUNDLE is None:
        raise ModelNotTrainedError(f"no model found at {MODEL_PATH.relative_to(REPO_ROOT)}; run ml/train.py first")

    home = _team_features(home_team_id, as_of)
    away = _team_features(away_team_id, as_of)

    row = {"postseason": int(postseason)}
    for key, value in home.items():
        row[f"home_{key}"] = value
    for key, value in away.items():
        row[f"away_{key}"] = value
    for window in (5, 10):
        row[f"win_pct_last{window}_diff"] = row[f"home_win_pct_last{window}"] - row[f"away_win_pct_last{window}"]
        row[f"point_diff_last{window}_diff"] = row[f"home_point_diff_last{window}"] - row[f"away_point_diff_last{window}"]
    row["win_pct_season_diff"] = row["home_win_pct_season"] - row["away_win_pct_season"]
    row["rest_days_diff"] = row["home_rest_days"] - row["away_rest_days"]

    features: list[str] = _BUNDLE["features"]
    X = pd.DataFrame([row])[features]
    home_win_probability = float(_BUNDLE["model"].predict_proba(X)[0, 1])

    return {
        "home_win_probability": home_win_probability,
        "away_win_probability": 1.0 - home_win_probability,
        "season": season_for_date(as_of),
        "home_form": home,
        "away_form": away,
        "model_version": MODEL_VERSION,
    }
