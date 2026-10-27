"""Pre-game features (ml/team_form.py): no leakage, and identical numbers
whether computed for training (add_pregame_features) or live serving
(team_form_as_of) - the guarantee that the API feeds the model what it learned on."""

import pandas as pd
import pytest

from team_form import (
    MIN_PRIOR_GAMES,
    REST_DAYS_CAP,
    ROLLING_WINDOWS,
    TEAM_FEATURES,
    elo_as_of,
    resolve_season,
    season_for_date,
    team_form_as_of,
)


@pytest.mark.parametrize(
    ("date", "season"),
    [("2024-10-22", 2024), ("2025-04-10", 2024), ("2025-06-20", 2024), ("2025-08-01", 2025), ("2025-01-01", 2024)],
)
def test_season_for_date(date, season):
    assert season_for_date(pd.Timestamp(date)) == season


def test_resolve_season_prefers_the_next_scheduled_game(long_df):
    team = long_df[long_df["team_id"] == 1]
    first_2024 = team[team["season"] == 2024]["date"].min()
    # A day before the 2024 opener, the next game on the schedule is a 2024 game.
    assert resolve_season(team, first_2024 - pd.Timedelta(days=1)) == 2024
    # Past the end of the data it falls back to the calendar guess.
    assert resolve_season(team, pd.Timestamp("2030-01-15")) == 2029


def test_rolling_form_uses_only_earlier_games(pregame):
    team = pregame[(pregame["team_id"] == 3) & (pregame["season"] == 2024)].sort_values("date")
    for i in [1, 4, 12, 18]:
        prior = team.iloc[:i]
        row = team.iloc[i]
        assert row["games_played_season"] == i
        assert row["win_pct_season"] == pytest.approx(prior["win"].mean())
        for w in ROLLING_WINDOWS:
            assert row[f"point_diff_last{w}"] == pytest.approx(prior["point_diff"].tail(w).mean())


def test_first_game_of_a_season_has_no_form(pregame):
    openers = pregame.sort_values("date").groupby(["team_id", "season"]).head(1)
    assert openers["win_pct_season"].isna().all()
    assert openers["point_diff_last5"].isna().all()


def test_rest_days_are_capped(pregame):
    assert pregame["rest_days"].max() <= REST_DAYS_CAP
    # The season break is months long, so the 2024 openers hit the cap.
    openers = pregame[pregame["season"] == 2024].sort_values("date").groupby("team_id").head(1)
    assert (openers["rest_days"] == REST_DAYS_CAP).all()
    known = pregame["rest_days"].notna()
    assert (pregame.loc[known, "is_back_to_back"] == (pregame.loc[known, "rest_days"] <= 1)).all()


def test_training_and_serving_features_are_identical(long_df, pregame):
    """For every game with enough history, the live snapshot taken on game day
    must equal the training row's features exactly."""
    rows = pregame[pregame["games_played_season"] >= MIN_PRIOR_GAMES]
    assert len(rows) > 150  # ~85% of the 248 team-games
    for row in rows.itertuples():
        live = team_form_as_of(long_df[long_df["team_id"] == row.team_id], row.date)
        assert live is not None
        for feature in TEAM_FEATURES:
            assert live[feature] == pytest.approx(getattr(row, feature), abs=1e-9), (row.game_id, feature)


def test_too_few_games_means_no_snapshot(long_df):
    team = long_df[(long_df["team_id"] == 2)].sort_values("date")
    season_games = team[team["season"] == 2024]
    early = season_games["date"].iloc[MIN_PRIOR_GAMES - 1]  # only MIN_PRIOR_GAMES - 1 games played before it
    assert team_form_as_of(team, early) is None
    assert team_form_as_of(team, season_games["date"].iloc[MIN_PRIOR_GAMES]) is not None


def test_elo_as_of_matches_pregame_elo_and_works_on_opening_night(long_df):
    team = long_df[long_df["team_id"] == 5].sort_values("date")
    for row in team.iloc[1:].itertuples():
        assert elo_as_of(team, row.date) == pytest.approx(row.elo, abs=1e-9)
    assert elo_as_of(team, team["date"].iloc[0]) is None  # nothing before the first game ever
