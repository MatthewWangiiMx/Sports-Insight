"""One-time copy of the local parquet files (data/raw/nba/) into Supabase.

Creates the tables if needed, then upserts every season, so it's safe to
re-run - rows already there are overwritten, never duplicated.

Usage (from ml/, with .venv active):
    python -m ingest.migrate_to_db
"""

from __future__ import annotations

import time

import pandas as pd

import raw_store
from ingest.run_nba_ingest import DATA_RAW_NBA


def main() -> None:
    if not raw_store.using_database():
        raise SystemExit("DATABASE_URL is not set in backend/.env")

    print("creating tables (if missing)...")
    raw_store.create_schema()

    print("teams:", raw_store.upsert("teams", pd.read_parquet(DATA_RAW_NBA / "teams.parquet")), "rows")
    for kind in ("team_games", "player_games"):
        for path in sorted(DATA_RAW_NBA.glob(f"{kind}_*.parquet")):
            start = time.perf_counter()
            n = raw_store.upsert(kind, pd.read_parquet(path))
            print(f"{path.stem}: {n} rows ({time.perf_counter() - start:.1f}s)")

    with raw_store.connect() as conn:
        for table in ("teams", "team_games", "player_games"):
            print(f"{table}: {conn.execute(f'select count(*) from {table}').fetchone()[0]} rows in database")


if __name__ == "__main__":
    main()
