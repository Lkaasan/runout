"""Polite, cache-first HTTP for the information finder.

- Honest user agent, one request at a time per host, with a minimum gap between requests.
- robots.txt is respected for ordinary websites. The documented public APIs (Wikipedia,
  MusicBrainz) are exempt: they are meant for programs and have their own rate rules.
- Responses are cached by full URL, so a repeat run makes no network calls.
- Retries with back-off when a server says it is busy (HTTP 429/503, or MusicBrainz's JSON notice).
"""

import json
import time
from collections.abc import Callable
from urllib.robotparser import RobotFileParser

import httpx

from app.pipeline.cache import HttpRecord, ResearchCache

USER_AGENT = "runout-info-finder/0.1 (+https://github.com/Lkaasan/runout)"
ROBOTS_TOKEN = "runout-info-finder"

# Documented public APIs: no robots.txt check.
API_HOSTS = ("wikipedia.org", "musicbrainz.org", "archive.org")

# Minimum seconds between requests to one host.
INTERVALS = {"musicbrainz.org": 1.1, "wikipedia.org": 0.2}
DEFAULT_INTERVAL = 1.0


class FetchError(Exception):
    pass


class NotFound(FetchError):
    pass


class RobotsDisallowed(FetchError):
    pass


def _host_matches(host: str, suffix: str) -> bool:
    return host == suffix or host.endswith("." + suffix)


def _looks_busy(text: str) -> bool:
    return text.lstrip().startswith('{"error"') and "busy" in text[:200].lower()


class Fetcher:
    def __init__(
        self,
        cache: ResearchCache,
        *,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        respect_robots: bool = True,
        refresh: bool = False,
        retries: int = 3,
        backoff: float = 2.0,
    ):
        self.cache = cache
        self.client = client or httpx.Client(timeout=30, follow_redirects=True)
        self._sleep, self._clock = sleep, clock
        self.respect_robots = respect_robots
        # Ignore cached responses and fetch again (the new response replaces the old one).
        self.refresh = refresh
        self.retries, self.backoff = retries, backoff
        self.network_calls = 0
        self.cache_hits = 0
        self._last: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser | None] = {}

    def get_text(self, url: str, params: dict | None = None, *, refresh: bool = False) -> str:
        return self.fetch(url, params, refresh=refresh).text

    def fetch(self, url: str, params: dict | None = None, *, refresh: bool = False) -> HttpRecord:
        """The response record (text and when it was really fetched), from cache when possible."""
        full = str(httpx.URL(url, params=params))
        if not (refresh or self.refresh) and (record := self.cache.get(full)) is not None:
            self.cache_hits += 1
            if record.status == 404:
                raise NotFound(full)
            return record

        host = httpx.URL(full).host
        self._check_robots(host, full)

        response, busy = None, False
        for attempt in range(self.retries + 1):
            self._throttle(host)
            response = self._get(full)
            busy = response.status_code in (429, 503) or (
                _host_matches(host, "musicbrainz.org") and _looks_busy(response.text)
            )
            if not busy or attempt == self.retries:
                break
            self._sleep(self.backoff * 2**attempt)

        assert response is not None
        if response.status_code == 404:
            self.cache.put(full, 404, "")
            raise NotFound(full)
        if busy or response.status_code != 200:
            raise FetchError(f"{full}: HTTP {response.status_code}{' (busy)' if busy else ''}")
        return self.cache.put(full, 200, response.text)

    def get_json(self, url: str, params: dict | None = None, *, refresh: bool = False):
        return json.loads(self.get_text(url, params, refresh=refresh))

    # ---- internals -----------------------------------------------------------------------

    def _get(self, url: str) -> httpx.Response:
        self.network_calls += 1
        self._last[httpx.URL(url).host] = self._clock()
        return self.client.get(url, headers={"User-Agent": USER_AGENT})

    def _throttle(self, host: str) -> None:
        interval = next(
            (v for k, v in INTERVALS.items() if _host_matches(host, k)), DEFAULT_INTERVAL
        )
        last = self._last.get(host)
        if last is not None:
            wait = interval - (self._clock() - last)
            if wait > 0:
                self._sleep(wait)

    def _check_robots(self, host: str, url: str) -> None:
        if not self.respect_robots or any(_host_matches(host, h) for h in API_HOSTS):
            return
        if host not in self._robots:
            parser: RobotFileParser | None = RobotFileParser()
            try:
                self.network_calls += 1
                resp = self.client.get(
                    f"https://{host}/robots.txt", headers={"User-Agent": USER_AGENT}
                )
                if resp.status_code == 200:
                    parser.parse(resp.text.splitlines())  # type: ignore[union-attr]
                else:
                    parser = None  # no robots.txt: everything allowed
            except httpx.HTTPError:
                parser = None
            self._robots[host] = parser
        parser = self._robots[host]
        if parser is not None and not parser.can_fetch(ROBOTS_TOKEN, url):
            raise RobotsDisallowed(f"robots.txt disallows {url}")
