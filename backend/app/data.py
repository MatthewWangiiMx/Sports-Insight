"""Loads teams/games (Supabase, or data/raw/nba/ parquet) into memory and keeps
them there.

At our data volume (~13k games) this is simpler and faster than querying per
request. A background thread (start_auto_refresh) checks every few minutes
whether the stored data changed - e.g. after the daily ingest - and if so
reloads and swaps everything in at once, so new games show up without a restart.
"""

from __future__ import annotations

import os
import sys
import threading
import time
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
# Overridable so tests can point the API at a small generated league instead.
DATA_RAW_NBA = Path(os.getenv("NBA_RAW_DIR") or REPO_ROOT / "data" / "raw" / "nba")

ML_DIR = REPO_ROOT / "ml"
if str(ML_DIR) not in sys.path:
    sys.path.insert(0, str(ML_DIR))

import raw_store  # noqa: E402
from nba_source import load_player_games, load_team_games, load_teams  # noqa: E402
from ratings import add_ratings  # noqa: E402

# How often the auto-refresh thread checks for new data, in seconds.
REFRESH_INTERVAL_SECONDS = int(os.getenv("DATA_REFRESH_SECONDS", "300"))

# Filled in by reload(). Module globals rather than a passed-around object so
# every function below always reads the latest snapshot.
TEAMS: pd.DataFrame
PLAYER_GAMES: pd.DataFrame
TEAM_GAMES_LONG: pd.DataFrame
LATEST_GAME_DATE: pd.Timestamp
LATEST_SEASON: int
DATA_VERSION: str = ""
LOADED_AT: pd.Timestamp
# Bumped on every reload; part of the league_advanced cache key so an old
# season table can't be served after new games arrive.
_GENERATION = 0
_reload_listeners: list[Callable[[], None]] = []
_reload_lock = threading.Lock()


def _current_version() -> str:
    try:
        return raw_store.data_version(DATA_RAW_NBA)
    except Exception as exc:  # database unreachable - force a reload once it's back
        print(f"[data] couldn't check data version ({exc.__class__.__name__}); will retry")
        return "unavailable"


def reload() -> None:
    """Load everything, then swap it in. Building first and assigning after
    means requests never see a half-loaded mix of old and new tables."""
    global TEAMS, PLAYER_GAMES, TEAM_GAMES_LONG, LATEST_GAME_DATE, LATEST_SEASON
    global DATA_VERSION, LOADED_AT, _GENERATION
    with _reload_lock:
        version = _current_version()  # taken before reading, so a change mid-read is caught next check
        teams = load_teams(DATA_RAW_NBA)
        player_games = load_player_games(DATA_RAW_NBA)
        team_games_long = add_ratings(load_team_games(DATA_RAW_NBA), player_games)

        TEAMS, PLAYER_GAMES, TEAM_GAMES_LONG = teams, player_games, team_games_long
        LATEST_GAME_DATE = team_games_long["date"].max()
        LATEST_SEASON = int(team_games_long["season"].max())
        DATA_VERSION, LOADED_AT = version, pd.Timestamp.now()
        _GENERATION += 1
        for listener in _reload_listeners:
            listener()


def on_reload(listener: Callable[[], None]) -> Callable[[], None]:
    """Register something (e.g. players.py's derived tables) to rebuild after each reload."""
    _reload_listeners.append(listener)
    return listener


def start_auto_refresh() -> None:
    def loop() -> None:
        while True:
            time.sleep(REFRESH_INTERVAL_SECONDS)
            try:
                if _current_version() not in (DATA_VERSION, "unavailable"):
                    started = time.perf_counter()
                    reload()
                    print(f"[data] reloaded in {time.perf_counter() - started:.1f}s; latest game {LATEST_GAME_DATE.date()}")
            except Exception as exc:  # keep serving the old data rather than kill the thread
                print(f"[data] auto-refresh failed: {exc.__class__.__name__}: {exc}")

    threading.Thread(target=loop, name="data-auto-refresh", daemon=True).start()


reload()

# Season-level advanced stats shown on the team page, and whether a higher value
# is better (for league ranking). Pace has no "better" - rank 1 = fastest.
ADVANCED_STATS = {
    "ppg": True,
    "opp_ppg": False,
    "off_rtg": True,
    "def_rtg": False,
    "net_rtg": True,
    "pace": True,
    "efg": True,
    "opp_efg": False,
    "tov_pct": False,
    "oreb_pct": True,
    "ft_rate": True,
}


def league_advanced(season: int) -> pd.DataFrame:
    return _league_advanced(season, _GENERATION)


@lru_cache(maxsize=64)
def _league_advanced(season: int, generation: int) -> pd.DataFrame:
    """Every team's regular-season advanced stats plus league ranks, indexed by
    team_id. Rates come from season *totals* (e.g. total points / total
    possessions), not the average of per-game rates, which would let a
    4-of-4 night count as much as a 12-of-20 one."""
    g = TEAM_GAMES_LONG[(TEAM_GAMES_LONG["season"] == season) & (~TEAM_GAMES_LONG["postseason"])]
    if g.empty:
        return pd.DataFrame()
    t = g.groupby("team_id")[
        ["team_score", "opp_score", "possessions", "fgm", "fg3m", "fga", "ftm", "fta", "tov", "oreb",
         "opp_fgm", "opp_fg3m", "opp_fga", "opp_dreb"]
    ].sum()
    games = g.groupby("team_id").size()
    out = pd.DataFrame(index=t.index)
    out["ppg"] = t["team_score"] / games
    out["opp_ppg"] = t["opp_score"] / games
    out["off_rtg"] = 100 * t["team_score"] / t["possessions"]
    out["def_rtg"] = 100 * t["opp_score"] / t["possessions"]
    out["net_rtg"] = out["off_rtg"] - out["def_rtg"]
    out["pace"] = t["possessions"] / games
    out["efg"] = (t["fgm"] + 0.5 * t["fg3m"]) / t["fga"]
    out["opp_efg"] = (t["opp_fgm"] + 0.5 * t["opp_fg3m"]) / t["opp_fga"]
    out["tov_pct"] = t["tov"] / (t["fga"] + 0.44 * t["fta"] + t["tov"])
    out["oreb_pct"] = t["oreb"] / (t["oreb"] + t["opp_dreb"])
    out["ft_rate"] = t["ftm"] / t["fga"]
    for stat, higher_is_better in ADVANCED_STATS.items():
        out[f"{stat}_rank"] = out[stat].rank(ascending=not higher_is_better, method="min").astype(int)
    return out


def season_elo(team_id: int, season: int) -> float | None:
    """Team's Elo after its most recent game of that season (playoffs included -
    Elo keeps learning from every game, unlike the regular-season record)."""
    g = team_games(team_id)
    g = g[g["season"] == season]
    return None if g.empty else float(g.sort_values("date")["elo_post"].iloc[-1])


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
            "elo": float(row["elo_post"]),
        }
        for _, row in games.iterrows()
    ]

    adv = league_advanced(season).loc[team_id]
    advanced = {stat: {"value": float(adv[stat]), "rank": int(adv[f"{stat}_rank"])} for stat in ADVANCED_STATS}

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
        "elo": season_elo(team_id, season),
        "advanced": advanced,
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
                "elo": season_elo(team["id"], season),
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
