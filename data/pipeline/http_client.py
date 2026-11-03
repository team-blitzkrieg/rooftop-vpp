"""Small HTTP helper: pause between calls, retry when a server is busy.

Open-Meteo and NASA POWER are free and keyless. Be polite. A 429 or a
dropped connection is retried with a growing wait. A 400 is not retried,
because the request itself is wrong.
"""

from __future__ import annotations

import time
from urllib.parse import urlsplit

import requests

from data.pipeline.config import USER_AGENT

RETRY_STATUSES = {429, 500, 502, 503, 504}


class HttpClient:
    def __init__(
        self,
        session: requests.Session | None = None,
        *,
        pause_s: float = 1.0,
        max_retries: int = 5,
        timeout_s: float = 120,
        sleep=time.sleep,
        monotonic=time.monotonic,
    ):
        if session is None:
            session = requests.Session()
            session.headers["User-Agent"] = USER_AGENT
        self.session = session
        self.pause_s = pause_s
        self.max_retries = max_retries
        self.timeout_s = timeout_s
        self._sleep = sleep
        self._monotonic = monotonic
        self._last_by_host: dict[str, float] = {}

    def get_json(self, url: str, params: dict) -> dict:
        host = urlsplit(url).netloc
        last_error: Exception | None = None
        attempts = self.max_retries + 1
        for attempt in range(attempts):
            self._pause(host)
            try:
                response = self.session.get(url, params=params, timeout=self.timeout_s)
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                self._sleep(self._backoff(attempt, None))
                continue

            if response.status_code in RETRY_STATUSES:
                last_error = requests.HTTPError(
                    f"HTTP {response.status_code} from {host}",
                    response=response,
                )
                if attempt >= self.max_retries:
                    break
                self._sleep(self._backoff(attempt, response))
                continue

            if response.status_code >= 400:
                text = (getattr(response, "text", "") or "")[:500]
                raise requests.HTTPError(
                    f"HTTP {response.status_code} from {url}: {text}",
                    response=response,
                )

            try:
                payload = response.json()
            except ValueError as exc:
                raise requests.HTTPError(f"Response from {url} was not JSON") from exc

            if isinstance(payload, dict) and payload.get("error"):
                reason = payload.get("reason") or payload
                raise requests.HTTPError(f"{url} returned an error: {reason}")
            return payload

        raise requests.HTTPError(
            f"Giving up on {url} after {attempts} tries: {last_error}"
        )

    def _pause(self, host: str) -> None:
        now = self._monotonic()
        if self.pause_s > 0:
            last = self._last_by_host.get(host)
            if last is not None:
                wait = self.pause_s - (now - last)
                if wait > 0:
                    self._sleep(wait)
                    now = self._monotonic()
        self._last_by_host[host] = now

    @staticmethod
    def _backoff(attempt: int, response) -> float:
        if response is not None:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    return min(120.0, float(retry_after))
                except ValueError:
                    pass
        return min(60.0, 2.0 ** (attempt + 1))
