import pytest

from app.models.enums import ClaimType
from app.pipeline.cache import ResearchCache
from app.pipeline.collect import collect_album
from app.pipeline.collectors.musicbrainz import MusicBrainzCollector
from app.pipeline.collectors.wikipedia import WikipediaCollector, track_key
from app.pipeline.http import Fetcher
from app.services.seed_loader import AlbumBundle
from app.services.seed_schema import AlbumSeed, ArtistSeed, ClaimSeed, TrackSeed
from tests.pipeline.fakeweb import ARTIST, FakeWeb


def fetcher_for(tmp_path, web: FakeWeb) -> Fetcher:
    return Fetcher(
        ResearchCache(tmp_path), client=web.client, sleep=lambda s: None, clock=lambda: 0.0
    )


# ---- title matching -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "a,b",
    [
        ("Pigs on the Wing, Part One", "Pigs on the Wing"),
        ("Pigs on the Wing (Part Two)", "Pigs on the Wing"),
        ("Pigs (Three Different Ones)", "Pigs"),
        ("Sheep", "Sheep (Pink Floyd song)"),
        ("Dogs", "dogs"),
    ],
)
def test_track_key_ignores_parts_and_parentheticals(a, b):
    assert track_key(a) == track_key(b)


def test_track_key_keeps_different_songs_apart():
    assert track_key("Pigs on the Wing") != track_key("Pigs (Three Different Ones)")


# ---- Wikipedia ----------------------------------------------------------------------------


def test_finds_the_album_article(tmp_path):
    wiki = WikipediaCollector(fetcher_for(tmp_path, FakeWeb()))
    assert wiki.find_album_title("Animals", ARTIST) == "Animals (Pink Floyd album)"
    assert wiki.find_album_title("Nonexistent", ARTIST) is None


def test_article_page_has_text_revision_and_all_pages_of_links(tmp_path):
    page = WikipediaCollector(fetcher_for(tmp_path, FakeWeb())).article(
        "Animals (Pink Floyd album)"
    )
    assert page is not None
    assert page.kind == "wikipedia" and "tenth studio album" in page.text
    assert page.url.endswith("Animals_(Pink_Floyd_album)?oldid=42")  # a citable revision
    assert page.meta["revid"] == 42
    assert page.meta["extlinks"] == [f"http://example.com/ref{i}" for i in range(3)]
    assert "Dogs (Pink Floyd song)" in page.meta["links"]


def test_missing_article_is_none(tmp_path):
    assert WikipediaCollector(fetcher_for(tmp_path, FakeWeb())).article("No such page") is None


def test_collects_song_articles_and_rejects_the_animal(tmp_path):
    pages, notes = WikipediaCollector(fetcher_for(tmp_path, FakeWeb())).collect(
        "Animals",
        ARTIST,
        [
            "Pigs on the Wing (Part One)",
            "Dogs",
            "Sheep",
            "Pigs on the Wing (Part Two)",
            "Pigs (Three Different Ones)",
        ],
    )
    titles = [p.title for p in pages]
    assert titles == [
        "Animals (Pink Floyd album)",
        "Pigs on the Wing",  # both parts share one article, collected once
        "Dogs (Pink Floyd song)",
        "Sheep (Pink Floyd song)",  # not the animal "Sheep"
    ]
    assert any("Pigs (Three Different Ones)" in n for n in notes)  # no such link in the fixture


def test_no_album_article_gives_a_note_not_an_error(tmp_path):
    pages, notes = WikipediaCollector(fetcher_for(tmp_path, FakeWeb())).collect(
        "Nonexistent", ARTIST, []
    )
    assert pages == [] and "No Wikipedia article" in notes[0]


# ---- MusicBrainz --------------------------------------------------------------------------


def test_musicbrainz_picks_the_exact_group_and_earliest_official_release(tmp_path):
    web = FakeWeb()
    pages, notes = MusicBrainzCollector(fetcher_for(tmp_path, web)).collect("Animals", ARTIST)
    assert notes == [] and len(pages) == 1
    page = pages[0]
    assert page.url.endswith("/release/294992a7-0000-0000-0000-000000000001")  # 1977, not 1994
    assert "Track 1: Dogs (17:00), ISRC GBDJQ7700005" in page.text
    assert "Credit: design - Storm Thorgerson" in page.text
    assert "Track 1 credit: instrument (guitar) - David Gilmour" in page.text
    assert page.meta["artist_ids"] == ["artist-1"]
    assert page.meta["tracks"][0]["length_ms"] == 1019666


def test_musicbrainz_unknown_album_gives_a_note(tmp_path):
    class Empty(FakeWeb):
        def _musicbrainz(self, request):
            return self._json({"release-groups": []})

    pages, notes = MusicBrainzCollector(fetcher_for(tmp_path, Empty())).collect("Zzz", ARTIST)
    assert pages == [] and "No MusicBrainz release group" in notes[0]


# ---- the whole collection -----------------------------------------------------------------


def bundle() -> AlbumBundle:
    claim = ClaimSeed(id="c", type=ClaimType.trivia, phase="before", body="x")
    track = lambda n, t: TrackSeed(number=n, title=t)  # noqa: E731
    return AlbumBundle(
        album=AlbumSeed(
            slug="animals", title="Animals", artist=ArtistSeed(name=ARTIST), claims=[claim]
        ),
        sources=[],
        tracks=[track(1, "Dogs"), track(2, "Sheep")],
    )


def test_collect_stores_pages_and_a_second_run_makes_no_requests(tmp_path):
    web = FakeWeb()
    cache = ResearchCache(tmp_path)
    first = collect_album(bundle(), Fetcher(cache, client=web.client, sleep=lambda s: None), cache)
    assert [p.kind for p in first.pages][0] == "musicbrainz"
    assert first.network_calls > 0 and len(first.pages) == 4  # MusicBrainz + album + 2 songs

    calls_before = len(web.calls)
    second = collect_album(bundle(), Fetcher(cache, client=web.client, sleep=lambda s: None), cache)
    assert len(web.calls) == calls_before
    assert second.network_calls == 0 and second.cache_hits > 0
    assert [p.text for p in second.pages] == [p.text for p in first.pages]

    stored = cache.get_pages("animals")
    assert [p.url for p in stored] == [p.url for p in first.pages]


def test_one_source_being_down_does_not_stop_the_other(tmp_path):
    web = FakeWeb(musicbrainz_down=True)
    cache = ResearchCache(tmp_path)
    fetcher = Fetcher(cache, client=web.client, sleep=lambda s: None, retries=1)
    report = collect_album(bundle(), fetcher, cache)
    assert {p.kind for p in report.pages} == {"wikipedia"}
    assert any("MusicBrainz unavailable" in n for n in report.notes)


def test_refresh_fetches_again(tmp_path):
    web = FakeWeb()
    cache = ResearchCache(tmp_path)
    collect_album(bundle(), Fetcher(cache, client=web.client, sleep=lambda s: None), cache)
    before = len(web.calls)
    collect_album(
        bundle(), Fetcher(cache, client=web.client, sleep=lambda s: None, refresh=True), cache
    )
    assert len(web.calls) > before


def test_cli_collect_reports_pages_and_exits_zero(tmp_path, monkeypatch, capsys):
    from app import research
    from app.config import settings

    web = FakeWeb()
    monkeypatch.setattr(settings, "research_cache_dir", tmp_path)
    monkeypatch.setattr(settings, "content_dir", tmp_path / "albums")
    monkeypatch.setattr(research, "load_album", lambda d, slug: bundle())
    real = research.Fetcher
    monkeypatch.setattr(
        research,
        "Fetcher",
        lambda cache, **kw: real(cache, client=web.client, sleep=lambda s: None, **kw),
    )
    assert research.main(["collect", "animals"]) == 0
    out = capsys.readouterr().out
    assert "Collected 4 page(s)" in out and "[musicbrainz]" in out
    assert research.main(["collect", "animals"]) == 0
    assert "Network requests: 0" in capsys.readouterr().out
