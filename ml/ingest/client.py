"""Thin client for the balldontlie NBA API (https://docs.balldontlie.io/).

Handles auth, cursor pagination, and free-tier rate limiting (5 req/min).
"""

from __future__ import annotations

import time
from typing import Any, Iterator

import requests

BASE_URL = "https://api.balldontlie.io/v1"


class RateLimiter:
    def __init__(self, min_interval_seconds: float):
        self.min_interval = min_interval_seconds
        self._last_call: float | None = None

    def wait(self) -> None:
        if self._last_call is not None:
            elapsed = time.monotonic() - self._last_call
            remaining = self.min_interval - elapsed
            if remaining > 0:
                time.sleep(remaining)
        self._last_call = time.monotonic()


class BallDontLieClient:
    def __init__(self, api_key: str, requests_per_minute: int = 5):
        if not api_key:
            raise ValueError("balldontlie API key is required")
        self.session = requests.Session()
        self.session.headers.update({"Authorization": api_key})
        self._limiter = RateLimiter(60.0 / requests_per_minute)

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{BASE_URL}{path}"
        for attempt in range(6):
            self._limiter.wait()
            resp = self.session.get(url, params=params, timeout=30)
            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", 15))
                print(f"  rate limited, waiting {retry_after:.0f}s...")
                time.sleep(retry_after)
                continue
            resp.raise_for_status()
            return resp.json()
        raise RuntimeError(f"Exceeded retries for {url}")

    def paginate(self, path: str, params: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
        params = dict(params or {})
        params.setdefault("per_page", 100)
        cursor: Any = None
        page = 0
        while True:
            page_params = dict(params)
            if cursor is not None:
                page_params["cursor"] = cursor
            payload = self._get(path, page_params)
            rows = payload.get("data", [])
            page += 1
            print(f"  {path} page {page}: {len(rows)} rows")
            yield from rows
            cursor = (payload.get("meta") or {}).get("next_cursor")
            if not cursor:
                break

    def get_teams(self) -> list[dict[str, Any]]:
        return list(self.paginate("/teams"))

    def get_games(self, season: int) -> list[dict[str, Any]]:
        return list(self.paginate("/games", {"seasons[]": season}))

    def get_stats(self, season: int) -> list[dict[str, Any]]:
        return list(self.paginate("/stats", {"seasons[]": season}))
