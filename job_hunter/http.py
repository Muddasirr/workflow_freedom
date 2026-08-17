from __future__ import annotations

import time
from typing import Any

import httpx

from job_hunter.config import USER_AGENT


class HttpClient:
    def __init__(self, timeout: float = 8.0) -> None:
        self._client = httpx.Client(
            timeout=timeout,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json, text/xml, */*"},
            follow_redirects=True,
        )

    def close(self) -> None:
        self._client.close()

    def get_json(self, url: str, *, params: dict[str, Any] | None = None, retries: int = 1) -> Any:
        last_error: Exception | None = None
        for attempt in range(retries):
            try:
                response = self._client.get(url, params=params)
                if response.status_code == 429:
                    time.sleep(1.2)
                    continue
                if response.status_code >= 500:
                    time.sleep(0.6)
                    continue
                response.raise_for_status()
                return response.json()
            except Exception as exc:  # noqa: BLE001 - sources are best-effort
                last_error = exc
                if attempt + 1 < retries:
                    time.sleep(0.4)
        raise last_error or RuntimeError(f"Failed to fetch {url}")

    def get_html(self, url: str, *, retries: int = 1) -> str:
        try:
            response = self._client.get(
                url,
                headers={"Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8"},
            )
            if response.status_code == 404:
                return ""
            if response.status_code >= 400:
                return ""
            return response.text
        except Exception:  # noqa: BLE001
            return ""

    def get_text(self, url: str, *, params: dict[str, Any] | None = None, retries: int = 1) -> str:
        last_error: Exception | None = None
        for attempt in range(retries):
            try:
                response = self._client.get(url, params=params)
                if response.status_code >= 400:
                    last_error = RuntimeError(f"{response.status_code} {url}")
                    continue
                return response.text
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt + 1 < retries:
                    time.sleep(0.4)
        raise last_error or RuntimeError(f"Failed to fetch {url}")
