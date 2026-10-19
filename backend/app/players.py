"""Player-level stats from the stats.nba.com player game logs loaded in data.py.

Season numbers are regular season only, matching the team pages. Shooting
percentages come from season totals (total makes / total attempts), not the
average of per-game percentages.
"""

from __future__ import annotations

import pandas as pd

from .data import PLAYER_GAMES

# Stats that can be ranked on the leaders board, and their display labels.
LEADER_STATS = {
    "pts": "Points",
    "reb": "Rebounds",
    "ast": "Assists",
    "stl": "Steals",
    "blk": "Blocks",
    "fg3m": "3-pointers made",
    "game_score": "Game Score",
}
# A player must have played at least this share of the season's games to
# appear on a leaders board - stops a 3-game cameo from topping the list.
LEADER_MIN_GAMES_SHARE = 0.5

_REGULAR = PLAYER_GAMES[~PLAYER_GAMES["postseason"]]

# One row per player: name, plus team and season from their most recent game.
_PLAYER_INDEX = (
    PLAYER_GAMES.sort_values("date")
    .groupby("player_id")
    .tail(1)[["player_id", "player_name", "team_abbreviation", "season"]]
    .rename(columns={"player_id": "id", "player_name": "name", "season": "last_season"})
    .sort_values(["last_season", "name"], ascending=[False, True])
)


def list_players() -> list[dict]:
    return _PLAYER_INDEX.to_dict(orient="records")


def _averages(rows: pd.DataFrame) -> dict:
    gp = len(rows)
    totals = rows[["min", "pts", "reb", "ast", "stl", "blk", "tov", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta"]].sum()

    def pct(made: str, att: str) -> float | None:
        return float(totals[made] / totals[att]) if totals[att] else None

    return {
        "games_played": int(gp),
        "min": float(totals["min"] / gp),
        "pts": float(totals["pts"] / gp),
        "reb": float(totals["reb"] / gp),
        "ast": float(totals["ast"] / gp),
        "stl": float(totals["stl"] / gp),
        "blk": float(totals["blk"] / gp),
        "tov": float(totals["tov"] / gp),
        "fg3m": float(totals["fg3m"] / gp),
        "fg_pct": pct("fgm", "fga"),
        "fg3_pct": pct("fg3m", "fg3a"),
        "ft_pct": pct("ftm", "fta"),
        "plus_minus": float(rows["plus_minus"].mean()),
        "game_score": float(rows["game_score"].mean()),
    }


def player_stats(player_id: int, season: int | None) -> dict | None:
    games = _REGULAR[_REGULAR["player_id"] == player_id]
    if games.empty:
        return None
    seasons = sorted(games["season"].unique().tolist())
    season = season if season is not None else seasons[-1]
    rows = games[games["season"] == season].sort_values("date")
    if rows.empty:
        return None

    # Teams in the order he played for them (more than one = traded mid-season).
    teams = rows.drop_duplicates("team_id")["team_abbreviation"].tolist()
    game_log = [
        {
            "date": r.date.date(),
            "team_abbreviation": r.team_abbreviation,
            "opponent_abbreviation": r.matchup.split()[-1],
            "is_home": bool(r.is_home),
            "win": r.wl == "W",
            "min": int(r.min),
            "pts": int(r.pts),
            "reb": int(r.reb),
            "ast": int(r.ast),
            "stl": int(r.stl),
            "blk": int(r.blk),
            "fgm": int(r.fgm),
            "fga": int(r.fga),
            "fg3m": int(r.fg3m),
            "fg3a": int(r.fg3a),
            "plus_minus": int(r.plus_minus),
            "game_score": float(r.game_score),
        }
        for r in rows.itertuples(index=False)
    ]
    return {
        "player_id": player_id,
        "name": rows["player_name"].iloc[-1],
        "season": season,
        "seasons": seasons,
        "teams": teams,
        "averages": _averages(rows),
        "game_log": game_log,
    }


def team_roster(team_id: int, season: int) -> list[dict]:
    """Everyone who played for the team that season, with their averages *for
    this team only* - a traded player shows just his games here."""
    rows = _REGULAR[(_REGULAR["team_id"] == team_id) & (_REGULAR["season"] == season)]
    roster = [
        {"player_id": int(pid), "name": g["player_name"].iloc[-1], **_averages(g)}
        for pid, g in rows.groupby("player_id")
    ]
    return sorted(roster, key=lambda p: p["min"] * p["games_played"], reverse=True)


def leaders(season: int, stat: str, limit: int) -> list[dict]:
    rows = _REGULAR[_REGULAR["season"] == season]
    if rows.empty:
        return []
    per_player = rows.groupby("player_id").agg(
        name=("player_name", "last"),
        team_abbreviation=("team_abbreviation", "last"),
        games_played=("game_id", "size"),
        value=(stat, "mean"),
    )
    qualified = per_player[per_player["games_played"] >= LEADER_MIN_GAMES_SHARE * per_player["games_played"].max()]
    top = qualified.nlargest(limit, "value").reset_index()
    return [
        {
            "rank": i + 1,
            "player_id": int(r.player_id),
            "name": r.name,
            "team_abbreviation": r.team_abbreviation,
            "games_played": int(r.games_played),
            "value": float(r.value),
        }
        for i, r in enumerate(top.itertuples(index=False))
    ]
