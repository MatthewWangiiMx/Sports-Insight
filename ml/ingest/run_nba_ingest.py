"""Pull team + player game logs from stats.nba.com (via nba_api) into data/raw/nba/.

Seasons are given by starting year, matching the rest of the pipeline
(2024 = the 2024-25 season). No API key needed.

Usage (from ml/, with .venv active):
    python -m ingest.run_nba_ingest --seasons 2016 2017 2018
    python -m ingest.run_nba_ingest --seasons 2025 --overwrite
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import pandas as pd
from nba_api.stats.endpoints import leaguegamelog, leaguestandingsv3
from nba_api.stats.static import teams as static_teams

import raw_store

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_RAW_NBA = REPO_ROOT / "data" / "raw" / "nba"

# stats.nba.com has no published rate limit but throttles bursts; a short pause
# between calls plus retries on timeout keeps a full multi-season pull reliable.
REQUEST_PAUSE_SECONDS = 0.8
MAX_ATTEMPTS = 4

SEASON_TYPES = {"Regular Season": False, "PlayIn": True, "Playoffs": True}


def season_label(start_year: int) -> str:
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def fetch(endpoint_cls, **kwargs) -> pd.DataFrame:
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            time.sleep(REQUEST_PAUSE_SECONDS)
            return endpoint_cls(timeout=60, **kwargs).get_data_frames()[0]
        except Exception as exc:
            if attempt == MAX_ATTEMPTS:
                raise
            wait = 5 * attempt
            print(f"  request failed ({exc.__class__.__name__}), retrying in {wait}s...")
            time.sleep(wait)
    raise AssertionError("unreachable")


def fetch_game_logs(start_year: int, kind: str) -> pd.DataFrame:
    """kind: 'T' for team logs, 'P' for player logs."""
    frames = []
    for season_type, is_postseason in SEASON_TYPES.items():
        df = fetch(
            leaguegamelog.LeagueGameLog,
            season=season_label(start_year),
            player_or_team_abbreviation=kind,
            season_type_all_star=season_type,
        )
        if df.empty:
            continue
        df["POSTSEASON"] = is_postseason
        frames.append(df)
    if not frames:
        # Season hasn't started yet (or no games logged so far).
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    out["SEASON"] = start_year
    out["IS_HOME"] = out["MATCHUP"].str.contains("vs.", regex=False)
    # Neutral-site games (international games, NBA Cup knockout rounds in Vegas)
    # list both teams with "@", so neither row is marked home.
    has_home = out.groupby("GAME_ID")["IS_HOME"].transform("any")
    out["NEUTRAL_SITE"] = ~has_home
    out["GAME_DATE"] = pd.to_datetime(out["GAME_DATE"])
    return out


def save(df: pd.DataFrame, path: Path, kind: str) -> None:
    """Write the local parquet copy, and upsert into Supabase when configured."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    print(f"  wrote {len(df)} rows -> {path.relative_to(REPO_ROOT)}")
    if raw_store.using_database():
        raw_store.upsert(kind, df)
        print(f"  upserted {len(df)} rows -> database table {kind}")


def save_teams(latest_season: int) -> None:
    # Static list has names/abbreviations but no conference/division; the
    # standings endpoint has those, so merge the two on team id.
    static = pd.DataFrame(static_teams.get_teams()).rename(columns={"nickname": "name"})
    standings = fetch(leaguestandingsv3.LeagueStandingsV3, season=season_label(latest_season))
    conf = standings[["TeamID", "Conference", "Division"]].rename(
        columns={"TeamID": "id", "Conference": "conference", "Division": "division"}
    )
    teams = static[["id", "city", "name", "full_name", "abbreviation"]].merge(conf, on="id", how="left")
    save(teams, DATA_RAW_NBA / "teams.parquet", "teams")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seasons", type=int, nargs="+", required=True, help="starting years, e.g. 2016 2017")
    parser.add_argument("--overwrite", action="store_true", help="refetch even if the output file already exists")
    args = parser.parse_args()

    for season in args.seasons:
        for kind, name in (("T", "team_games"), ("P", "player_games")):
            out = DATA_RAW_NBA / f"{name}_{season}.parquet"
            if out.exists() and not args.overwrite:
                print(f"{name} {season}: already exists, skipping (use --overwrite to refetch)")
                continue
            print(f"{name} {season} ({season_label(season)}): fetching...")
            df = fetch_game_logs(season, kind)
            if df.empty:
                print("  no games yet, skipping")
                continue
            save(df, out, name)

    print("teams: fetching conference/division from latest season standings...")
    save_teams(max(args.seasons))


if __name__ == "__main__":
    main()
