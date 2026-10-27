"""API endpoints, served from the generated league (see tests/conftest.py)."""

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import data
from app.main import app
from synthetic import TEAM_IDS, TRADE_SEASON, TRADED_PLAYER_ID

# No `with` block: skips the app's startup hook, so no auto-refresh thread.
client = TestClient(app)


def test_health_reports_data_source():
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["source"] == "parquet"
    assert body["latest_game_date"] == str(data.LATEST_GAME_DATE.date())


def test_teams_list_and_lookup():
    teams = client.get("/teams").json()
    assert sorted(t["id"] for t in teams) == TEAM_IDS
    assert client.get("/teams/1").json()["abbreviation"] == "ANT"
    assert client.get("/teams/999").status_code == 404


def test_team_stats_count_regular_season_only(long_df):
    body = client.get("/teams/1/stats", params={"season": 2023}).json()
    regular = long_df[(long_df["team_id"] == 1) & (long_df["season"] == 2023) & ~long_df["postseason"]]
    assert body["games_played"] == len(regular)
    assert body["wins"] == int(regular["win"].sum())
    assert body["wins"] + body["losses"] == body["games_played"]
    assert len(body["game_log"]) == len(regular)
    assert body["advanced"]["net_rtg"]["rank"] in range(1, len(TEAM_IDS) + 1)


def test_team_stats_default_to_latest_season():
    assert client.get("/teams/1/stats").json()["season"] == data.LATEST_SEASON


def test_neutral_site_games_count_in_record_but_not_home_away_splits():
    for team_id in TEAM_IDS:
        b = client.get(f"/teams/{team_id}/stats", params={"season": 2024}).json()
        split_games = b["home_wins"] + b["home_losses"] + b["away_wins"] + b["away_losses"]
        assert split_games <= b["games_played"]
    totals = [client.get(f"/teams/{t}/stats", params={"season": 2024}).json() for t in TEAM_IDS]
    # Exactly two teams played the one neutral-site game.
    assert sum(b["games_played"] - (b["home_wins"] + b["home_losses"] + b["away_wins"] + b["away_losses"]) for b in totals) == 2


def test_unknown_season_is_404():
    assert client.get("/teams/1/stats", params={"season": 1999}).status_code == 404


def test_standings_ranks_and_games_behind():
    rows = client.get("/standings", params={"season": 2023}).json()
    assert len(rows) == len(TEAM_IDS)
    for conf in ("East", "West"):
        conf_rows = [r for r in rows if r["team"]["conference"] == conf]
        leader = min(conf_rows, key=lambda r: r["conference_rank"])
        assert leader["conference_rank"] == 1 and leader["games_behind"] == 0
        assert all(r["games_behind"] >= 0 for r in conf_rows)
        # Better win % never ranks lower.
        by_rank = sorted(conf_rows, key=lambda r: r["conference_rank"])
        assert [r["win_pct"] for r in by_rank] == sorted((r["win_pct"] for r in by_rank), reverse=True)


def test_head_to_head_is_symmetric():
    ab = client.get("/teams/1/vs/2").json()
    ba = client.get("/teams/2/vs/1").json()
    assert ab["team_a_wins"] == ba["team_b_wins"] and ab["team_b_wins"] == ba["team_a_wins"]
    assert ab["games_played"] == ab["team_a_wins"] + ab["team_b_wins"] > 0


def test_traded_player_shows_both_teams_and_split_rosters():
    body = client.get(f"/players/{TRADED_PLAYER_ID}/stats", params={"season": TRADE_SEASON}).json()
    assert body["teams"] == ["ANT", "BRV"]
    on_roster = {}
    for team_id in (1, 2):
        roster = client.get(f"/teams/{team_id}/roster", params={"season": TRADE_SEASON}).json()
        on_roster[team_id] = next(p["games_played"] for p in roster if p["player_id"] == TRADED_PLAYER_ID)
    # Each roster counts only his games for that team; together they make his season.
    assert on_roster[1] + on_roster[2] == body["averages"]["games_played"]


def test_player_percentages_come_from_totals(raw_dir):
    body = client.get("/players/101/stats", params={"season": 2023}).json()
    pg = pd.read_parquet(raw_dir / "player_games_2023.parquet")
    rows = pg[(pg["PLAYER_ID"] == 101) & ~pg["POSTSEASON"]]
    assert body["averages"]["fg_pct"] == pytest.approx(rows["FGM"].sum() / rows["FGA"].sum())


def test_unknown_player_is_404():
    assert client.get("/players/424242/stats").status_code == 404


def test_leaders_sorted_and_validated():
    rows = client.get("/leaders", params={"stat": "pts", "season": 2023, "limit": 5}).json()
    assert [r["rank"] for r in rows] == [1, 2, 3, 4, 5]
    assert [r["value"] for r in rows] == sorted((r["value"] for r in rows), reverse=True)
    assert client.get("/leaders", params={"stat": "nonsense"}).status_code == 400
    assert len(client.get("/leaders", params={"stat": "reb", "limit": 500}).json()) <= 50
