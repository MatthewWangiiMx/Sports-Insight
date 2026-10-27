"""Loading raw game logs into the long table, and the per-game stats derived there."""

import pandas as pd
import pytest

from nba_source import load_player_games, load_team_games, load_teams
from synthetic import DNP_PLAYER_SLOT, TEAM_IDS


def test_two_rows_per_game_each_seeing_the_other_as_opponent(raw_dir):
    df = load_team_games(raw_dir)
    assert (df.groupby("game_id").size() == 2).all()
    for _, game in df.groupby("game_id"):
        a, b = game.iloc[0], game.iloc[1]
        assert (a.team_id, a.opponent_id) == (b.opponent_id, b.team_id)
        assert a.team_score == b.opp_score and a.opp_score == b.team_score


def test_win_and_point_diff_agree_with_scores(raw_dir):
    df = load_team_games(raw_dir)
    assert (df["point_diff"] == df["team_score"] - df["opp_score"]).all()
    assert (df["win"] == (df["point_diff"] > 0)).all()
    # Every game has exactly one winner.
    assert (df.groupby("game_id")["win"].sum() == 1).all()


def test_advanced_stats_match_their_formulas(raw_dir):
    row = load_team_games(raw_dir).iloc[0]
    team_poss = row.fga - row.oreb + row.tov + 0.44 * row.fta
    opp_poss = row.opp_fga - row.opp_oreb + row.opp_tov + 0.44 * row.opp_fta
    possessions = (team_poss + opp_poss) / 2
    assert row.possessions == pytest.approx(possessions)
    assert row.off_rtg == pytest.approx(100 * row.team_score / possessions)
    assert row.net_rtg == pytest.approx(row.off_rtg - row.def_rtg)
    assert row.efg == pytest.approx((row.fgm + 0.5 * row.fg3m) / row.fga)
    assert row.oreb_pct == pytest.approx(row.oreb / (row.oreb + row.opp_dreb))


def test_long_table_sorted_by_team_then_date(raw_dir):
    df = load_team_games(raw_dir)
    for _, g in df.groupby("team_id"):
        assert g["date"].is_monotonic_increasing


def test_players_who_never_played_are_dropped(raw_dir):
    pg = load_player_games(raw_dir)
    assert (pg["min"] > 0).all()
    assert not (pg["player_id"] % 100 == DNP_PLAYER_SLOT).any()


def test_game_score_formula(raw_dir):
    r = load_player_games(raw_dir).iloc[0]
    expected = (
        r.pts + 0.4 * r.fgm - 0.7 * r.fga - 0.4 * (r.fta - r.ftm) + 0.7 * r.oreb + 0.3 * r.dreb
        + r.stl + 0.7 * r.ast + 0.7 * r.blk - 0.4 * r.pf - r.tov
    )
    assert r.game_score == pytest.approx(expected)


def test_teams_sorted_by_name(raw_dir):
    teams = load_teams(raw_dir)
    assert sorted(teams["id"]) == TEAM_IDS
    assert teams["full_name"].tolist() == sorted(teams["full_name"])
    assert isinstance(teams, pd.DataFrame)
