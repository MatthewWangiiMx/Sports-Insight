"""raw_store (database/parquet switch) and the ingest's secret handling."""

import pandas as pd
import pytest

import raw_store
from ingest import run_nba_ingest


@pytest.fixture
def fresh_conninfo(monkeypatch):
    """_conninfo() is cached; clear it around each test so env changes apply."""
    monkeypatch.delenv("DATA_SOURCE", raising=False)
    monkeypatch.setattr(raw_store, "load_env", lambda: None)  # never read the real backend/.env
    raw_store._conninfo.cache_clear()
    yield
    raw_store._conninfo.cache_clear()


def test_database_url_with_special_characters_in_password(monkeypatch, fresh_conninfo):
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://postgres.abc123:p@ss:w#rd%@aws-0-us-east-1.pooler.supabase.com:5432/postgres"
    )
    info = raw_store._conninfo()
    assert info["user"] == "postgres.abc123"
    assert info["password"] == "p@ss:w#rd%"  # taken literally - no percent-encoding needed
    assert info["host"] == "aws-0-us-east-1.pooler.supabase.com"
    assert info["port"] == 5432
    assert info["dbname"] == "postgres"
    assert info["sslmode"] == "require"


def test_no_database_url_means_parquet(monkeypatch, fresh_conninfo):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert raw_store.using_database() is False


def test_data_source_parquet_overrides_database_url(monkeypatch, fresh_conninfo):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host:5432/db")
    monkeypatch.setenv("DATA_SOURCE", "parquet")
    assert raw_store.using_database() is False


def test_unreachable_database_falls_back_to_parquet(monkeypatch, raw_dir, capsys):
    monkeypatch.setattr(raw_store, "using_database", lambda: True)

    def broken(_table):
        raise ConnectionError("project paused")

    monkeypatch.setattr(raw_store, "_read_table", broken)
    df = raw_store.read("team_games", raw_dir)
    assert len(df) > 0 and "game_id" in df.columns
    assert "using parquet" in capsys.readouterr().out


def test_failed_requests_never_print_the_proxy_password(monkeypatch, capsys):
    secret_proxy = "http://someone:TopSecret123@10.0.0.1:8080"
    monkeypatch.setenv("NBA_PROXY", secret_proxy)
    monkeypatch.setattr(run_nba_ingest.raw_store, "load_env", lambda: None)
    monkeypatch.setattr(run_nba_ingest.time, "sleep", lambda _s: None)

    class FailingEndpoint:
        def __init__(self, **kwargs):
            # Real request libraries put the full proxy URL in some error messages.
            raise ValueError(f"Failed to parse: {kwargs['proxy']}")

    with pytest.raises(RuntimeError) as exc_info:
        run_nba_ingest.fetch(FailingEndpoint)
    shown = str(exc_info.value) + capsys.readouterr().out
    assert "TopSecret123" not in shown
    assert exc_info.value.__cause__ is None and exc_info.value.__suppress_context__


def test_upsert_of_nothing_is_a_no_op():
    # Returns before touching the database, so this needs no connection.
    assert raw_store.upsert("team_games", pd.DataFrame()) == 0
