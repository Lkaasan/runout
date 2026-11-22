import httpx
import pytest

from app.pipeline.cache import ResearchCache
from app.pipeline.http import (
    USER_AGENT,
    Fetcher,
    FetchError,
    NotFound,
    RobotsDisallowed,
)
from tests.pipeline.fakeweb import FakeWeb


def make(tmp_path, web: FakeWeb | None = None, **kw):
    web = web or FakeWeb()
    sleeps: list[float] = []
    now = [0.0]

    def sleep(s: float) -> None:
        sleeps.append(s)
        now[0] += s

    fetcher = Fetcher(
        ResearchCache(tmp_path), client=web.client, sleep=sleep, clock=lambda: now[0], **kw
    )
    return fetcher, web, sleeps


def test_second_identical_request_is_served_from_cache(tmp_path):
    fetcher, web, _ = make(tmp_path)
    first = fetcher.get_text("https://example.com/a")
    second = fetcher.get_text("https://example.com/a")
    assert first == second == "ok"
    assert (fetcher.network_calls, fetcher.cache_hits) == (2, 1)  # robots.txt + page, then cache
    assert len([c for c in web.calls if c.endswith("/a")]) == 1


def test_params_are_part_of_the_cache_key(tmp_path):
    fetcher, web, _ = make(tmp_path)
    fetcher.get_text(
        "https://en.wikipedia.org/w/api.php", {"titles": "A", "action": "query", "prop": "extracts"}
    )
    fetcher.get_text(
        "https://en.wikipedia.org/w/api.php", {"titles": "B", "action": "query", "prop": "extracts"}
    )
    assert len(web.calls) == 2


def test_refresh_fetches_again_and_replaces_the_cache(tmp_path):
    fetcher, web, _ = make(tmp_path, respect_robots=False)
    fetcher.get_text("https://example.com/a")
    fetcher.get_text("https://example.com/a", refresh=True)
    assert len(web.calls) == 2


def test_sends_an_honest_user_agent(tmp_path):
    seen = []
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda r: (seen.append(r.headers["user-agent"]), httpx.Response(200, text="x"))[1]
        )
    )
    Fetcher(ResearchCache(tmp_path), client=client, respect_robots=False).get_text(
        "https://a.test/x"
    )
    assert seen == [USER_AGENT] and "runout" in USER_AGENT


def test_404_is_cached_and_raised(tmp_path):
    fetcher, web, _ = make(tmp_path)
    for _ in range(2):
        with pytest.raises(NotFound):
            fetcher.get_text("https://musicbrainz.org/ws/2/nothing")
    assert len(web.calls) == 1


def test_busy_server_is_retried_with_backoff(tmp_path):
    fetcher, web, sleeps = make(tmp_path, FakeWeb(busy_musicbrainz=2), backoff=2.0)
    data = fetcher.get_json(
        "https://musicbrainz.org/ws/2/release-group", {"query": "x", "fmt": "json"}
    )
    assert "release-groups" in data
    assert len(web.calls) == 3
    assert sleeps[:1] == [2.0] and 4.0 in sleeps


def test_gives_up_after_retries_and_caches_nothing(tmp_path):
    fetcher, web, _ = make(tmp_path, FakeWeb(musicbrainz_down=True), retries=2)
    with pytest.raises(FetchError, match="busy"):
        fetcher.get_text("https://musicbrainz.org/ws/2/release-group")
    assert len(web.calls) == 3
    assert fetcher.cache.get("https://musicbrainz.org/ws/2/release-group") is None


def test_requests_to_one_host_are_spaced(tmp_path):
    fetcher, _, sleeps = make(tmp_path)
    fetcher.get_text("https://musicbrainz.org/ws/2/release-group", {"query": "a"})
    fetcher.get_text("https://musicbrainz.org/ws/2/release-group", {"query": "b"})
    assert sleeps and sleeps[-1] == pytest.approx(1.1)


def test_robots_txt_blocks_disallowed_paths_on_ordinary_sites(tmp_path):
    fetcher, web, _ = make(tmp_path)
    with pytest.raises(RobotsDisallowed):
        fetcher.get_text("https://example.com/private/page")
    assert not [c for c in web.calls if c.endswith("/private/page")]
    assert fetcher.get_text("https://example.com/public") == "ok"
    assert len([c for c in web.calls if c.endswith("/robots.txt")]) == 1  # fetched once per host


def test_documented_apis_skip_robots(tmp_path):
    fetcher, web, _ = make(tmp_path)
    fetcher.get_text("https://musicbrainz.org/ws/2/release-group", {"query": "a"})
    assert not [c for c in web.calls if "robots.txt" in c]
