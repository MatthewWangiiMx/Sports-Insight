"""Team strength ratings that build on game-by-game history: Elo, and roster
strength from player game logs. Shared by training and serving, like team_form.

add_ratings() attaches four columns to the team-centric long table:
  elo              - team's Elo *before* the game (a pre-game feature)
  elo_post         - team's Elo *after* the game (what a later game starts from)
  roster_strength  - value of the roster from the team's *previous* game
  roster_after     - value of the roster that played *this* game
The "pre" columns are what the model sees for a game; the "post" columns are
what live predictions read off a team's most recent game.
"""

from __future__ import annotations

import pandas as pd

# FiveThirtyEight-style NBA Elo.
ELO_START = 1500.0
ELO_K = 20
ELO_HOME_ADVANTAGE = 100
ELO_MEAN = 1505.0
# Between seasons ratings are pulled 25% of the way back toward the mean, since
# rosters turn over and last season's strength only partly carries forward.
ELO_CARRYOVER = 0.75

# A player's value is his average Game Score over his last N games (any team,
# so it travels with him on a trade); a roster's value is the sum of its best N
# players' values - roughly the rotation that decides games.
PLAYER_VALUE_WINDOW = 20
ROSTER_TOP_N = 8


def carry_over(elo: float) -> float:
    return ELO_CARRYOVER * elo + (1 - ELO_CARRYOVER) * ELO_MEAN


def add_ratings(long_df: pd.DataFrame, player_games: pd.DataFrame) -> pd.DataFrame:
    long_df = long_df.merge(_elo_history(long_df), on=["game_id", "team_id"], how="left")
    long_df = long_df.merge(_roster_after(player_games), on=["game_id", "team_id"], how="left")
    long_df = long_df.sort_values(["team_id", "date"]).reset_index(drop=True)
    # Previous game's roster = who we'd assume is available next (we never know
    # injuries in advance, so the same rule is used in training and serving).
    long_df["roster_strength"] = long_df.groupby("team_id")["roster_after"].shift(1)
    return long_df


def _elo_history(long_df: pd.DataFrame) -> pd.DataFrame:
    """Walks every game in date order, recording each team's rating before and
    after. The pre-game rating is fixed before the result is applied, so it
    can never include the game it's used to predict."""
    # One row per game: the home side, or for neutral sites an arbitrary side (no home edge).
    side = long_df[
        long_df["is_home"] | (long_df["neutral_site"] & (long_df["team_id"] < long_df["opponent_id"]))
    ].sort_values(["date", "game_id"])

    rating: dict[int, float] = {}
    season_of: dict[int, int] = {}
    rows = []
    for g in side[["game_id", "season", "team_id", "opponent_id", "team_score", "opp_score", "neutral_site"]].itertuples(index=False):
        for team in (g.team_id, g.opponent_id):
            if team not in rating:
                rating[team] = ELO_START
            elif season_of[team] != g.season:
                rating[team] = carry_over(rating[team])
            season_of[team] = g.season

        home, away = rating[g.team_id], rating[g.opponent_id]
        edge = 0 if g.neutral_site else ELO_HOME_ADVANTAGE
        expected_home = 1 / (1 + 10 ** (-(home + edge - away) / 400))
        home_won = g.team_score > g.opp_score

        # Margin-of-victory multiplier: bigger wins move ratings more, damped when
        # the favorite wins big (that's expected, so it's less informative).
        margin = abs(g.team_score - g.opp_score)
        winner_edge = (home + edge - away) if home_won else (away - home - edge)
        multiplier = ((margin + 3) ** 0.8) / (7.5 + 0.006 * winner_edge)
        shift = ELO_K * multiplier * (float(home_won) - expected_home)

        rating[g.team_id] = home + shift
        rating[g.opponent_id] = away - shift
        rows.append((g.game_id, g.team_id, home, home + shift))
        rows.append((g.game_id, g.opponent_id, away, away - shift))

    return pd.DataFrame(rows, columns=["game_id", "team_id", "elo", "elo_post"])


def _roster_after(player_games: pd.DataFrame) -> pd.DataFrame:
    pg = player_games[["player_id", "team_id", "game_id", "date", "game_score"]].sort_values(["player_id", "date"])
    # Value *through* each game (includes it) - only ever read by later games.
    pg["value"] = (
        pg.groupby("player_id")["game_score"]
        .rolling(PLAYER_VALUE_WINDOW, min_periods=1)
        .mean()
        .reset_index(level=0, drop=True)
    )
    pg = pg.sort_values(["team_id", "game_id", "value"], ascending=[True, True, False])
    top = pg[pg.groupby(["team_id", "game_id"]).cumcount() < ROSTER_TOP_N]
    return top.groupby(["team_id", "game_id"], as_index=False)["value"].sum().rename(columns={"value": "roster_after"})
