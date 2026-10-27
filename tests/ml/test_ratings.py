"""Elo and roster strength (ml/ratings.py)."""

import pandas as pd
import pytest

from ratings import ELO_HOME_ADVANTAGE, ELO_MEAN, ELO_START, carry_over, elo_win_probability


def test_elo_probability_basics():
    assert elo_win_probability(1500, 1500, neutral_site=True) == pytest.approx(0.5)
    # Home court alone is worth the same as a 100-point rating edge on neutral ground.
    assert elo_win_probability(1500, 1500) == pytest.approx(
        elo_win_probability(1500 + ELO_HOME_ADVANTAGE, 1500, neutral_site=True)
    )
    assert elo_win_probability(1500, 1500) > 0.5
    # On neutral ground the two sides' chances add up to 1.
    assert elo_win_probability(1600, 1450, True) + elo_win_probability(1450, 1600, True) == pytest.approx(1)
    assert elo_win_probability(1700, 1500) > elo_win_probability(1600, 1500)


def test_carry_over_pulls_toward_the_mean():
    assert carry_over(ELO_MEAN) == pytest.approx(ELO_MEAN)
    high, low = carry_over(1700), carry_over(1300)
    assert ELO_MEAN < high < 1700
    assert 1300 < low < ELO_MEAN


def test_everyone_starts_at_the_initial_rating(long_df):
    first_games = long_df.sort_values("date").groupby("team_id").head(1)
    assert (first_games["elo"] == ELO_START).all()


def test_elo_is_zero_sum_per_game(long_df):
    shift = (long_df["elo_post"] - long_df["elo"]).groupby(long_df["game_id"]).sum()
    assert shift.abs().max() == pytest.approx(0, abs=1e-9)


def test_winner_gains_and_loser_drops(long_df):
    change = long_df["elo_post"] - long_df["elo"]
    assert (change[long_df["win"] == 1] > 0).all()
    assert (change[long_df["win"] == 0] < 0).all()


def test_each_game_starts_from_the_previous_games_rating(long_df):
    for _, g in long_df.groupby("team_id"):
        g = g.sort_values("date")
        same_season = g["season"].eq(g["season"].shift(1))
        prev_post = g["elo_post"].shift(1)
        assert (g["elo"][same_season] - prev_post[same_season]).abs().max() == pytest.approx(0, abs=1e-9)
        # Across the season break the rating is regressed toward the mean.
        first_of_season = ~same_season & prev_post.notna()
        expected = prev_post[first_of_season].map(carry_over)
        assert (g["elo"][first_of_season] - expected).abs().max() == pytest.approx(0, abs=1e-9)


def test_roster_strength_is_the_previous_games_roster(long_df):
    for _, g in long_df.groupby("team_id"):
        g = g.sort_values("date")
        assert pd.isna(g["roster_strength"].iloc[0])
        pd.testing.assert_series_equal(
            g["roster_strength"].iloc[1:].reset_index(drop=True),
            g["roster_after"].iloc[:-1].reset_index(drop=True),
            check_names=False,
        )
