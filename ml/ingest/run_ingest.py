"""Pull teams/games/stats from balldontlie into data/raw/ as parquet files.

Usage (from ml/, with .venv active):
    python -m ingest.run_ingest --seasons 2022 2023 2024
    python -m ingest.run_ingest --seasons 2023 --resources teams games
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from ingest.client import BallDontLieClient

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = REPO_ROOT / "data" / "raw"


def save(rows: list[dict], path: Path) -> None:
    if not rows:
        print(f"  no rows returned, skipping {path.name}")
        return
    df = pd.json_normalize(rows, sep="_")
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    print(f"  wrote {len(df)} rows -> {path.relative_to(REPO_ROOT)}")


def main() -> None:
    load_dotenv(REPO_ROOT / ".env")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seasons", type=int, nargs="+", required=True, help="e.g. --seasons 2022 2023 2024")
    parser.add_argument(
        "--resources",
        nargs="+",
        choices=["teams", "games", "stats"],
        default=["teams", "games", "stats"],
    )
    parser.add_argument("--requests-per-minute", type=int, default=5, help="match your balldontlie plan's limit")
    parser.add_argument("--overwrite", action="store_true", help="refetch even if the output file already exists")
    args = parser.parse_args()

    api_key = os.environ.get("BALLDONTLIE_API_KEY")
    if not api_key:
        sys.exit("BALLDONTLIE_API_KEY not set. Add it to a .env file at the repo root (see .env.example).")

    client = BallDontLieClient(api_key, requests_per_minute=args.requests_per_minute)

    if "teams" in args.resources:
        out = DATA_RAW / "teams.parquet"
        if out.exists() and not args.overwrite:
            print(f"teams: {out.name} already exists, skipping (use --overwrite to refetch)")
        else:
            print("teams: fetching...")
            save(client.get_teams(), out)

    for season in args.seasons:
        if "games" in args.resources:
            out = DATA_RAW / f"games_{season}.parquet"
            if out.exists() and not args.overwrite:
                print(f"games {season}: {out.name} already exists, skipping (use --overwrite to refetch)")
            else:
                print(f"games {season}: fetching...")
                save(client.get_games(season), out)

        if "stats" in args.resources:
            out = DATA_RAW / f"stats_{season}.parquet"
            if out.exists() and not args.overwrite:
                print(f"stats {season}: {out.name} already exists, skipping (use --overwrite to refetch)")
            else:
                print(f"stats {season}: fetching...")
                try:
                    save(client.get_stats(season), out)
                except Exception as exc:
                    print(f"  stats {season} failed ({exc}); likely requires a paid balldontlie plan. Skipping.")


if __name__ == "__main__":
    main()
