"""Where the raw stats.nba.com data lives: Supabase Postgres when DATABASE_URL is
set, otherwise the local parquet files in data/raw/nba/.

The database holds exactly what the ingest pulls (one row per team-game, one
per player-game, plus the teams list) - nothing derived. Elo, form and advanced
stats are recomputed in Python on load, so fixing a past game never leaves a
stale derived value behind.

Shared by ml/ (ingest, training) and the backend, same as nba_source.py.
"""

from __future__ import annotations

import io
import json
import os
from functools import lru_cache
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = REPO_ROOT / "backend" / ".env"
# Local copy of the last database read, reused while the database is unchanged.
CACHE_DIR = REPO_ROOT / "data" / "raw" / "nba" / ".db_cache"

# kind -> (table, primary key). Column names are the lowercased nba_api ones.
TABLES = {
    "team_games": ("team_games", ["game_id", "team_id"]),
    "player_games": ("player_games", ["game_id", "player_id"]),
    "teams": ("teams", ["id"]),
}

_COMMON_GAME_COLS = """
    season_id text, team_id bigint, team_abbreviation text, team_name text,
    game_id text not null, game_date date not null, matchup text, wl text, min integer,
    fgm integer, fga integer, fg_pct double precision, fg3m integer, fg3a integer,
    fg3_pct double precision, ftm integer, fta integer, ft_pct double precision,
    oreb integer, dreb integer, reb integer, ast integer, stl integer, blk integer,
    tov integer, pf integer, pts integer, plus_minus integer, video_available integer,
    postseason boolean, season integer not null, is_home boolean, neutral_site boolean
"""

SCHEMA_SQL = f"""
create table if not exists teams (
    id bigint primary key, city text, name text, full_name text,
    abbreviation text, conference text, division text
);
create table if not exists team_games (
    {_COMMON_GAME_COLS},
    primary key (game_id, team_id)
);
create table if not exists player_games (
    player_id bigint not null, player_name text, fantasy_pts double precision,
    {_COMMON_GAME_COLS},
    primary key (game_id, player_id)
);
create index if not exists team_games_season_idx on team_games (season);
create index if not exists player_games_season_idx on player_games (season);
""" + "".join(
    # Bumped on every insert/update, so (row count, latest ingested_at) changes
    # whenever anything in a table does - see _fingerprint().
    f"alter table {t} add column if not exists ingested_at timestamptz not null default now();\n"
    for t in ("teams", "team_games", "player_games")
)


@lru_cache(maxsize=1)
def _conninfo() -> dict | None:
    """Connection settings from DATABASE_URL, or None to use parquet.

    The URL is split by hand instead of with a URL parser so a password
    containing '@', '#' or '%' works without having to percent-encode it.
    """
    from dotenv import load_dotenv

    load_dotenv(ENV_FILE)
    if os.getenv("DATA_SOURCE", "").lower() == "parquet":
        return None
    url = os.getenv("DATABASE_URL", "").strip().strip("'\"")
    if not url:
        return None

    rest = url.split("://", 1)[1]
    userinfo, hostinfo = rest.rsplit("@", 1)  # the host can't contain '@'; the password can
    user, password = userinfo.split(":", 1)
    hostport, _, dbname = hostinfo.partition("/")
    host, _, port = hostport.partition(":")
    return {
        "host": host,
        "port": int(port or 5432),
        "user": user,
        "password": password,
        "dbname": dbname.split("?", 1)[0] or "postgres",
        "sslmode": "require",
        "connect_timeout": 15,
    }


def using_database() -> bool:
    return _conninfo() is not None


def connect():
    import psycopg

    info = _conninfo()
    if info is None:
        raise RuntimeError("DATABASE_URL is not set (see backend/.env)")
    return psycopg.connect(**info)


def create_schema() -> None:
    with connect() as conn:
        conn.execute(SCHEMA_SQL)


def upsert(kind: str, df: pd.DataFrame) -> int:
    """Insert rows, replacing any with the same primary key. Safe to re-run.

    Bulk-loads into a temp table with COPY (fast even for 250k+ rows), then
    merges into the real table in one statement.
    """
    table, key = TABLES[kind]
    df = df.rename(columns=str.lower)
    if df.empty:
        return 0
    cols = list(df.columns)
    col_list = ", ".join(cols)
    updates = ", ".join([*(f"{c} = excluded.{c}" for c in cols if c not in key), "ingested_at = now()"])

    out = df.copy()
    if "game_date" in out:
        out["game_date"] = pd.to_datetime(out["game_date"]).dt.strftime("%Y-%m-%d")
    buf = io.StringIO()
    out.to_csv(buf, index=False, header=False)

    with connect() as conn:
        conn.execute(f"create temp table staging (like {table} including defaults) on commit drop")
        with conn.cursor().copy(f"copy staging ({col_list}) from stdin with (format csv)") as copy:
            copy.write(buf.getvalue())
        conn.execute(
            f"insert into {table} ({col_list}) select {col_list} from staging "
            f"on conflict ({', '.join(key)}) do update set {updates}"
        )
    return len(df)


def _fingerprint(conn, table: str) -> str:
    count, latest = conn.execute(f"select count(*), max(ingested_at) from {table}").fetchone()
    return f"{count}|{latest.isoformat() if latest else ''}"


def _read_table(table: str) -> pd.DataFrame:
    """Download a table, or reuse the local cache if the table hasn't changed."""
    cache_file = CACHE_DIR / f"{table}.parquet"
    meta_file = CACHE_DIR / f"{table}.json"
    with connect() as conn:
        fingerprint = _fingerprint(conn, table)
        if cache_file.exists() and meta_file.exists():
            if json.loads(meta_file.read_text()).get("fingerprint") == fingerprint:
                return pd.read_parquet(cache_file)
        df = _download(conn, table)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache_file, index=False)
    meta_file.write_text(json.dumps({"fingerprint": fingerprint}))
    return df


def _download(conn, table: str) -> pd.DataFrame:
    buf = io.BytesIO()
    with conn.cursor().copy(f"copy {table} to stdout with (format csv, header)") as copy:
        for chunk in copy:
            buf.write(chunk)
    buf.seek(0)
    df = pd.read_csv(
        buf,
        dtype={"game_id": str, "season_id": str},
        true_values=["t"],
        false_values=["f"],
        keep_default_na=False,
        na_values=[""],
    )
    if "game_date" in df:
        df["game_date"] = pd.to_datetime(df["game_date"])
    return df.drop(columns="ingested_at")


def _read_parquet(raw_dir: Path, kind: str) -> pd.DataFrame:
    if kind == "teams":
        return pd.read_parquet(raw_dir / "teams.parquet")
    files = sorted(raw_dir.glob(f"{kind}_*.parquet"))
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True).rename(columns=str.lower)


def read(kind: str, raw_dir: Path) -> pd.DataFrame:
    """Raw rows for one kind, lowercase columns. Falls back to parquet if the
    database can't be reached, so the site still runs offline."""
    if using_database():
        try:
            return _read_table(TABLES[kind][0])
        except Exception as exc:  # network down, project paused, ...
            print(f"[raw_store] database read failed ({exc.__class__.__name__}: {exc}); using parquet")
    return _read_parquet(raw_dir, kind)


def latest_game_date() -> pd.Timestamp | None:
    """Cheap freshness check - lets the backend notice new data without reloading everything."""
    with connect() as conn:
        value = conn.execute("select max(game_date) from team_games").fetchone()[0]
    return pd.Timestamp(value) if value else None
