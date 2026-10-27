"""A small generated league in the exact raw format the ingest writes
(data/raw/nba/*.parquet), so tests run anywhere - including CI, which has no
real NBA data - and can check exact numbers.

6 teams, 2 seasons (2023, 2024), 60 regular-season games each plus 2 playoff
games. Built in on purpose:
  - team strength differs (team 1 strongest), so Elo and records spread out
  - varied rest days, including back-to-backs
  - one neutral-site game (both sides listed with "@")
  - a bench player who never gets minutes (rows with MIN 0 must be dropped)
  - a player traded mid-season from team 1 to team 2
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

TEAMS = pd.DataFrame(
    [
        (1, "Alpha", "Ants", "Alpha Ants", "ANT", "East", "Atlantic"),
        (2, "Bravo", "Bears", "Bravo Bears", "BRV", "East", "Atlantic"),
        (3, "Charlie", "Comets", "Charlie Comets", "CHC", "East", "Central"),
        (4, "Delta", "Dragons", "Delta Dragons", "DLT", "West", "Pacific"),
        (5, "Echo", "Eagles", "Echo Eagles", "ECH", "West", "Pacific"),
        (6, "Foxtrot", "Foxes", "Foxtrot Foxes", "FOX", "West", "Northwest"),
    ],
    columns=["id", "city", "name", "full_name", "abbreviation", "conference", "division"],
)
TEAM_IDS = TEAMS["id"].tolist()
SEASONS = [2023, 2024]
# Higher = better shooting, so stronger teams win more often.
STRENGTH = {1: 3, 2: 2, 3: 1, 4: 0, 5: -1, 6: -2}

PLAYERS_PER_TEAM = 9  # the 9th never plays (MIN 0)
DNP_PLAYER_SLOT = 9
TRADED_PLAYER_ID = 105  # team 1 -> team 2 ...
TRADE_SEASON, TRADE_ROUND = 2024, 10  # ... from this round of this season on
NEUTRAL_SEASON, NEUTRAL_ROUND = 2024, 12  # first game of this round is at a neutral site


def player_id(team_id: int, slot: int) -> int:
    return team_id * 100 + slot


def _round_robin(team_ids: list[int]) -> list[list[tuple[int, int]]]:
    """Circle method: each round, every team plays exactly once."""
    teams = list(team_ids)
    rounds = []
    for _ in range(len(teams) - 1):
        rounds.append([(teams[i], teams[-1 - i]) for i in range(len(teams) // 2)])
        teams = [teams[0], teams[-1], *teams[1:-1]]
    return rounds


def _team_box(rng: np.random.Generator, strength: int) -> dict:
    fga = int(rng.integers(80, 96))
    fg3a = int(rng.integers(28, 43))
    fg3m = int(rng.binomial(fg3a, 0.33 + 0.012 * strength))
    fg2m = int(rng.binomial(fga - fg3a, 0.50 + 0.02 * strength))
    fta = int(rng.integers(15, 29))
    ftm = int(rng.binomial(fta, 0.78))
    oreb, dreb = int(rng.integers(8, 15)), int(rng.integers(30, 39))
    box = {
        "FGM": fg2m + fg3m, "FGA": fga, "FG3M": fg3m, "FG3A": fg3a, "FTM": ftm, "FTA": fta,
        "OREB": oreb, "DREB": dreb, "REB": oreb + dreb,
        "AST": int(rng.integers(20, 31)), "STL": int(rng.integers(5, 11)), "BLK": int(rng.integers(3, 8)),
        "TOV": int(rng.integers(10, 17)), "PF": int(rng.integers(16, 23)),
    }
    box["PTS"] = 2 * box["FGM"] + box["FG3M"] + box["FTM"]
    return box


def _player_box(rng: np.random.Generator) -> dict:
    fga = int(rng.integers(4, 21))
    fg3a = int(rng.integers(0, min(8, fga) + 1))
    fg3m = int(rng.binomial(fg3a, 0.35))
    fg2m = int(rng.binomial(fga - fg3a, 0.5))
    fta = int(rng.integers(0, 9))
    ftm = int(rng.binomial(fta, 0.78))
    oreb, dreb = int(rng.integers(0, 4)), int(rng.integers(1, 9))
    box = {
        "MIN": int(rng.integers(12, 39)), "FGM": fg2m + fg3m, "FGA": fga, "FG3M": fg3m, "FG3A": fg3a,
        "FTM": ftm, "FTA": fta, "OREB": oreb, "DREB": dreb, "REB": oreb + dreb,
        "AST": int(rng.integers(0, 10)), "STL": int(rng.integers(0, 4)), "BLK": int(rng.integers(0, 3)),
        "TOV": int(rng.integers(0, 5)), "PF": int(rng.integers(0, 6)),
    }
    box["PTS"] = 2 * box["FGM"] + box["FG3M"] + box["FTM"]
    return box


def _pct(made: int, att: int) -> float:
    return round(made / att, 3) if att else np.nan


def _roster(team_id: int, season: int, rnd: int) -> list[int]:
    slots = [player_id(team_id, s) for s in range(1, PLAYERS_PER_TEAM + 1)]
    traded = (season, rnd) >= (TRADE_SEASON, TRADE_ROUND) and season == TRADE_SEASON
    if traded and team_id == 1:
        slots.remove(TRADED_PLAYER_ID)
    if traded and team_id == 2:
        slots.append(TRADED_PLAYER_ID)
    return slots


def _season_games(rng: np.random.Generator, season: int) -> list[dict]:
    """Schedule: 4 round-robin cycles (home/away alternating), then 2 playoff games."""
    base = _round_robin(TEAM_IDS)
    games, day, n = [], pd.Timestamp(f"{season}-10-22"), 0
    for cycle in range(4):
        for rnd_idx, pairs in enumerate(base):
            rnd = cycle * len(base) + rnd_idx
            for i, (a, b) in enumerate(pairs):
                home, away = (a, b) if cycle % 2 == 0 else (b, a)
                n += 1
                neutral = (season, rnd, i) == (NEUTRAL_SEASON, NEUTRAL_ROUND, 0)
                games.append(dict(game_id=f"002{season % 100:02d}{n:05d}", date=day, home=home, away=away,
                                  postseason=False, neutral=neutral, rnd=rnd))
            day += pd.Timedelta(days=int(rng.choice([1, 2, 2, 3])))  # 1 = back-to-back
    for k in range(2):
        day += pd.Timedelta(days=2)
        games.append(dict(game_id=f"004{season % 100:02d}{k + 1:05d}", date=day, home=1 if k == 0 else 2,
                          away=2 if k == 0 else 1, postseason=True, neutral=False, rnd=99))
    return games


def build_league(seed: int = 7) -> tuple[pd.DataFrame, dict[int, pd.DataFrame], dict[int, pd.DataFrame]]:
    """Returns (teams, team_games by season, player_games by season), raw nba_api columns."""
    rng = np.random.default_rng(seed)
    meta = TEAMS.set_index("id")
    team_by_season: dict[int, pd.DataFrame] = {}
    player_by_season: dict[int, pd.DataFrame] = {}

    for season in SEASONS:
        team_rows, player_rows = [], []
        for g in _season_games(rng, season):
            box = {g["home"]: _team_box(rng, STRENGTH[g["home"]]), g["away"]: _team_box(rng, STRENGTH[g["away"]])}
            if box[g["home"]]["PTS"] == box[g["away"]]["PTS"]:  # no ties in basketball
                box[g["home"]]["FTM"] += 1
                box[g["home"]]["FTA"] += 1
                box[g["home"]]["PTS"] += 1

            for team, opp in ((g["home"], g["away"]), (g["away"], g["home"])):
                is_home = team == g["home"] and not g["neutral"]
                sep = "vs." if is_home else "@"
                margin = box[team]["PTS"] - box[opp]["PTS"]
                common = {
                    "SEASON_ID": f"{4 if g['postseason'] else 2}{season}",
                    "TEAM_ID": team, "TEAM_ABBREVIATION": meta.at[team, "abbreviation"],
                    "TEAM_NAME": meta.at[team, "full_name"], "GAME_ID": g["game_id"], "GAME_DATE": g["date"],
                    "MATCHUP": f"{meta.at[team, 'abbreviation']} {sep} {meta.at[opp, 'abbreviation']}",
                    "WL": "W" if margin > 0 else "L",
                }
                flags = {"POSTSEASON": g["postseason"], "SEASON": season, "IS_HOME": is_home, "NEUTRAL_SITE": g["neutral"]}
                b = box[team]
                team_rows.append({
                    **common, "MIN": 240, **{k: b[k] for k in ("FGM", "FGA")}, "FG_PCT": _pct(b["FGM"], b["FGA"]),
                    "FG3M": b["FG3M"], "FG3A": b["FG3A"], "FG3_PCT": _pct(b["FG3M"], b["FG3A"]),
                    "FTM": b["FTM"], "FTA": b["FTA"], "FT_PCT": _pct(b["FTM"], b["FTA"]),
                    **{k: b[k] for k in ("OREB", "DREB", "REB", "AST", "STL", "BLK", "TOV", "PF", "PTS")},
                    "PLUS_MINUS": margin, "VIDEO_AVAILABLE": 1, **flags,
                })
                for pid in _roster(team, season, g["rnd"]):
                    dnp = pid % 100 == DNP_PLAYER_SLOT
                    p = {k: 0 for k in _player_box(rng)} if dnp else _player_box(rng)
                    player_rows.append({
                        "SEASON_ID": common["SEASON_ID"], "PLAYER_ID": pid, "PLAYER_NAME": f"Player {pid}",
                        **{k: v for k, v in common.items() if k != "SEASON_ID"},
                        "MIN": p["MIN"], "FGM": p["FGM"], "FGA": p["FGA"], "FG_PCT": _pct(p["FGM"], p["FGA"]),
                        "FG3M": p["FG3M"], "FG3A": p["FG3A"], "FG3_PCT": _pct(p["FG3M"], p["FG3A"]),
                        "FTM": p["FTM"], "FTA": p["FTA"], "FT_PCT": _pct(p["FTM"], p["FTA"]),
                        **{k: p[k] for k in ("OREB", "DREB", "REB", "AST", "STL", "BLK", "TOV", "PF", "PTS")},
                        "PLUS_MINUS": 0 if dnp else margin, "FANTASY_PTS": float(p["PTS"]), "VIDEO_AVAILABLE": 1, **flags,
                    })
        team_by_season[season] = pd.DataFrame(team_rows)
        player_by_season[season] = pd.DataFrame(player_rows)
    return TEAMS.copy(), team_by_season, player_by_season


def write_league(raw_dir: Path, seed: int = 7) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    teams, team_games, player_games = build_league(seed)
    teams.to_parquet(raw_dir / "teams.parquet", index=False)
    for season in SEASONS:
        team_games[season].to_parquet(raw_dir / f"team_games_{season}.parquet", index=False)
        player_games[season].to_parquet(raw_dir / f"player_games_{season}.parquet", index=False)
