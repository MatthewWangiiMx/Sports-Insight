"""Daily update: re-pull the current season from stats.nba.com into parquet and
Supabase. Past seasons never change, so only the current one is fetched
(about 7 requests, under a minute).

Re-pulling the whole season (rather than just "yesterday") is deliberate: it
also picks up stat corrections the NBA makes to earlier games, and the upsert
means unchanged rows are simply overwritten with themselves.

Usage (from ml/, with .venv active):
    python -m ingest.update               # current season, from today's date
    python -m ingest.update --season 2025 # a specific season
Runs daily on GitHub Actions (.github/workflows/daily-update.yml); scripts/daily_update.ps1
runs the same thing from a Windows PC.
"""

from __future__ import annotations

import argparse
import time

import pandas as pd

import raw_store
from ingest.run_nba_ingest import DATA_RAW_NBA, nba_proxy, fetch_game_logs, save, save_teams, season_label, write_parquet
from team_form import season_for_date


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, help="starting year; defaults to the season in progress today")
    args = parser.parse_args()

    season = args.season if args.season is not None else season_for_date(pd.Timestamp.today())
    started = time.perf_counter()
    targets = [name for name, on in (("parquet", write_parquet()), ("database", raw_store.using_database())) if on]
    if not targets:
        raise SystemExit("nowhere to save: DATABASE_URL is not set and WRITE_PARQUET=0")
    via = "via proxy" if nba_proxy() else "direct"
    print(f"updating {season_label(season)} season -> {' + '.join(targets)} ({via})")

    for kind, name in (("T", "team_games"), ("P", "player_games")):
        print(f"{name}: fetching...")
        df = fetch_game_logs(season, kind)
        if df.empty:
            print("  no games yet")
            continue
        print(f"  {df['GAME_ID'].nunique()} games, latest {df['GAME_DATE'].max().date()}")
        save(df, DATA_RAW_NBA / f"{name}_{season}.parquet", name)

    # Conference/division rarely change, but a failed standings call shouldn't
    # throw away the game logs we just saved - keep the old teams table instead.
    try:
        save_teams(season)
    except Exception as exc:
        print(f"teams: refresh failed ({exc.__class__.__name__}), keeping existing table")

    print(f"done in {time.perf_counter() - started:.0f}s")


if __name__ == "__main__":
    main()
