"""/predict/winprob: the trained model's live predictions, and the early-season
Elo fallback."""

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import model
from app.main import app
from prepare_features import build_game_features
from ratings import elo_win_probability
from team_form import MIN_PRIOR_GAMES, MODEL_FEATURES, elo_as_of

client = TestClient(app)

needs_model = pytest.mark.skipif(model._BUNDLE is None, reason=f"{model.MODEL_PATH.name} not present")


def predict(**body):
    return client.post("/predict/winprob", json=body)


def test_rejects_same_team_and_unknown_teams():
    assert predict(home_team_id=1, away_team_id=1).status_code == 400
    assert predict(home_team_id=1, away_team_id=999).status_code == 404


@needs_model
def test_mid_season_uses_the_model():
    r = predict(home_team_id=1, away_team_id=6, game_date="2024-12-20")
    assert r.status_code == 200
    body = r.json()
    assert body["model_version"] == model.MODEL_VERSION
    assert body["note"] is None
    assert 0 < body["home_win_probability"] < 1
    assert body["home_win_probability"] + body["away_win_probability"] == pytest.approx(1)
    assert 0 < len(body["factors"]) <= model.TOP_FACTOR_COUNT
    assert all(f["favors"] in ("home", "away") and f["impact_pct"] >= 0 for f in body["factors"])


@needs_model
def test_live_prediction_matches_offline_inference(pregame):
    """The plan's API check: for a past game, the endpoint must give exactly
    what the trained pipeline gives on that game's training-table row."""
    games = build_game_features(pregame.copy())
    games = games[(games["home_games_played_season"] >= MIN_PRIOR_GAMES) & (games["away_games_played_season"] >= MIN_PRIOR_GAMES)]
    pipeline = model._BUNDLE["model"]
    for game in games.sample(15, random_state=0).itertuples():
        offline = pipeline.predict_proba(pd.DataFrame([game._asdict()])[MODEL_FEATURES])[0, 1]
        live = model.predict_home_win_probability(game.home_team_id, game.away_team_id, game.date, bool(game.postseason))
        assert live["home_win_probability"] == pytest.approx(offline, abs=1e-9)


def test_early_season_falls_back_to_elo(long_df):
    # A day after every team's 2024 opener: one game each, too few for the model.
    openers = long_df[long_df["season"] == 2024].groupby("team_id")["date"].min()
    as_of = openers.max() + pd.Timedelta(days=1)
    r = predict(home_team_id=1, away_team_id=6, game_date=str(as_of.date()))
    assert r.status_code == 200
    body = r.json()
    assert body["model_version"] == model.ELO_FALLBACK_VERSION
    assert "Early-season estimate" in body["note"]

    home_elo = elo_as_of(long_df[long_df["team_id"] == 1], as_of)
    away_elo = elo_as_of(long_df[long_df["team_id"] == 6], as_of)
    assert body["home_win_probability"] == pytest.approx(elo_win_probability(home_elo, away_elo))
    # The two factors add back up to the gap from a coin flip.
    edge = sum(f["impact_pct"] if f["favors"] == "home" else -f["impact_pct"] for f in body["factors"])
    assert edge == pytest.approx((body["home_win_probability"] - 0.5) * 100)


def test_before_a_teams_first_game_ever_is_rejected(long_df):
    first_day = long_df["date"].min()
    assert predict(home_team_id=1, away_team_id=2, game_date=str(first_day.date())).status_code == 422
