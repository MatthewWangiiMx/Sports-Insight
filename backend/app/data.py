"""Loads teams/games from data/raw/nba/ once at process start and keeps them in memory.

At our data volume (~13k games) this is simpler and faster than hitting disk
or the upstream API per request, and it *is* the caching layer for now -
refreshing means re-running ml/ingest/run_nba_ingest and restarting the API.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
DATA_RAW_NBA = REPO_ROOT / "data" / "raw" / "nba"

ML_DIR = REPO_ROOT / "ml"
if str(ML_DIR) not in sys.path:
    sys.path.insert(0, str(ML_DIR))

from nba_source import load_team_games, load_teams  # noqa: E402

TEAMS = load_teams(DATA_RAW_NBA)
TEAM_GAMES_LONG = load_team_games(DATA_RAW_NBA)
LATEST_GAME_DATE: pd.Timestamp = TEAM_GAMES_LONG["date"].max()
LATEST_SEASON = int(TEAM_GAMES_LONG["season"].max())


def get_team(team_id: int) -> dict | None:
    row = TEAMS[TEAMS["id"] == team_id]
    return None if row.empty else row.iloc[0].to_dict()


def list_teams() -> list[dict]:
    return TEAMS.to_dict(orient="records")


def team_games(team_id: int) -> pd.DataFrame:
    return TEAM_GAMES_LONG[TEAM_GAMES_LONG["team_id"] == team_id]


def team_season_stats(team_id: int, season: int) -> dict | None:
    games = team_games(team_id)
    # Regular season only - mixing in playoff games would skew win_pct for teams
    # that went on a deep playoff run vs teams that didn't make the playoffs at all.
    games = games[(games["season"] == season) & (~games["postseason"])].sort_values("date")
    if games.empty:
        return None

    wins = int(games["win"].sum())
    losses = len(games) - wins
    home_games = games[games["is_home"]]
    # Neutral-site games count toward the overall record but neither split.
    away_games = games[~games["is_home"] & ~games["neutral_site"]]
    home_wins = int(home_games["win"].sum())
    away_wins = int(away_games["win"].sum())

    # Current streak: the trailing run of identical results, most recent game first.
    results = games["win"].tolist()
    streak_result = results[-1]
    streak_len = 0
    for r in reversed(results):
        if r != streak_result:
            break
        streak_len += 1
    current_streak = f"{'W' if streak_result == 1 else 'L'}{streak_len}"

    abbr_by_id = TEAMS.set_index("id")["abbreviation"]
    game_log = [
        {
            "date": row["date"].date(),
            "opponent_abbreviation": abbr_by_id.get(row["opponent_id"], "???"),
            "is_home": bool(row["is_home"]),
            "win": bool(row["win"]),
            "point_diff": int(row["point_diff"]),
        }
        for _, row in games.iterrows()
    ]

    return {
        "team_id": team_id,
        "season": season,
        "games_played": int(len(games)),
        "wins": wins,
        "losses": losses,
        "win_pct": float(games["win"].mean()),
        "avg_point_diff": float(games["point_diff"].mean()),
        "home_wins": home_wins,
        "home_losses": int(len(home_games)) - home_wins,
        "away_wins": away_wins,
        "away_losses": int(len(away_games)) - away_wins,
        "current_streak": current_streak,
        "game_log": game_log,
    }


def season_standings(season: int) -> list[dict]:
    rows = []
    for team in TEAMS.to_dict(orient="records"):
        games = team_games(team["id"])
        games = games[(games["season"] == season) & (~games["postseason"])]
        if games.empty:
            continue
        wins = int(games["win"].sum())
        total = int(len(games))
        rows.append(
            {
                "team": team,
                "season": season,
                "wins": wins,
                "losses": total - wins,
                "win_pct": wins / total,
                "conference": team["conference"],
                "division": team["division"],
            }
        )
    if not rows:
        return []

    df = pd.DataFrame(rows)
    df["conference_rank"] = df.groupby("conference")["win_pct"].rank(ascending=False, method="min").astype(int)
    df["division_rank"] = df.groupby("division")["win_pct"].rank(ascending=False, method="min").astype(int)

    leader_idx = df.groupby("conference")["win_pct"].idxmax()
    leaders = df.loc[leader_idx, ["conference", "wins", "losses"]].rename(
        columns={"wins": "leader_wins", "losses": "leader_losses"}
    )
    df = df.merge(leaders, on="conference")
    df["games_behind"] = ((df["leader_wins"] - df["wins"]) + (df["losses"] - df["leader_losses"])) / 2

    df = df.sort_values(["conference", "win_pct"], ascending=[True, False])
    return df.drop(columns=["conference", "division", "leader_wins", "leader_losses"]).to_dict(orient="records")


def head_to_head(team_a_id: int, team_b_id: int) -> dict:
    matchups = team_games(team_a_id)
    matchups = matchups[matchups["opponent_id"] == team_b_id].sort_values("date")

    games_played = int(len(matchups))
    team_a_wins = int(matchups["win"].sum())
    team_b_wins = games_played - team_a_wins

    last_meeting_date = None
    last_meeting_winner_id = None
    if games_played:
        last = matchups.iloc[-1]
        last_meeting_date = last["date"].date()
        last_meeting_winner_id = team_a_id if last["win"] == 1 else team_b_id

    return {
        "team_a_wins": team_a_wins,
        "team_b_wins": team_b_wins,
        "games_played": games_played,
        "last_meeting_date": last_meeting_date,
        "last_meeting_winner_id": last_meeting_winner_id,
    }


def default_as_of() -> pd.Timestamp:
    """Day after the most recent game we have data for.

    There's no live feed, so "predict as of right now" only makes sense in
    terms of the data we've actually ingested - this lands on whatever
    season's final games were most recently pulled.
    """
    return LATEST_GAME_DATE + pd.Timedelta(days=1)
