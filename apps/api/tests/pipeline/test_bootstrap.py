import json

import pytest

from app.pipeline.bootstrap import (
    iso_duration_ms,
    parse_music_album,
    pick_research_urls,
    slugify,
    structured_page_candidates,
    write_skeleton,
)
from app.pipeline.cache import ResearchCache
from app.pipeline.collectors.wikipedia import WikipediaCollector
from app.pipeline.http import Fetcher
from app.services.seed_loader import load_album
from tests.pipeline import fakeweb
from tests.pipeline.fakeweb import FakeWeb


def page(ld: dict) -> str:
    return f'<html><script type="application/ld+json">{json.dumps(ld)}</script></html>'


APPLE = page(
    {
        "@type": "MusicAlbum",
        "name": "It Goes On",
        "datePublished": "2026-08-21",
        "byArtist": [
            {
                "@type": "MusicGroup",
                "name": "Westside Cowboy",
                "url": "https://music.apple.com/us/artist/x/1798933328",
            }
        ],
        "image": "https://is1-ssl.mzstatic.com/image/thumb/Music/abc/cover.jpg/1200x630bb.jpg",
        "tracks": [
            {
                "@type": "MusicRecording",
                "name": "Kick Stones (The Boys)",
                "duration": "PT3M56S",
                "url": "https://music.apple.com/us/song/kick-stones/6767652037",
            },
            {
                "@type": "MusicRecording",
                "name": "Dobro",
                "duration": "PT2M45S",
                "url": "https://music.apple.com/us/song/dobro/6767652039",
            },
        ],
    }
)
BANDCAMP = page(
    {
        "@type": "MusicAlbum",
        "name": "It Goes On",
        "datePublished": "21 Aug 2026 00:00:00 GMT",
        "byArtist": {"@type": "MusicGroup", "name": "Westside Cowboy"},
        "image": "https://f4.bcbits.com/img/a0706145901_10.jpg",
        "track": {
            "@type": "ItemList",
            "itemListElement": [
                {
                    "position": 1,
                    "item": {
                        "@type": "MusicRecording",
                        "name": "Paper Chains",
                        "duration": "P00H02M51S",
                    },
                }
            ],
        },
    }
)


def test_durations_in_both_notations():
    assert iso_duration_ms("PT3M56S") == 236_000
    assert iso_duration_ms("P00H03M10S") == 190_000
    assert iso_duration_ms("PT1H2M3S") == 3_723_000
    assert iso_duration_ms("garbage") is None and iso_duration_ms(None) is None


def test_apple_music_page_gives_ids_lengths_and_a_square_cover():
    info = parse_music_album(APPLE, "https://music.apple.com/us/album/it-goes-on/6767652034")
    assert (info.title, info.artist, info.release_date) == (
        "It Goes On",
        "Westside Cowboy",
        "2026-08-21",
    )
    assert info.apple_music_id == "6767652034" and info.artist_apple_music_id == "1798933328"
    assert [(t.number, t.title, t.duration_ms, t.apple_music_id) for t in info.tracks] == [
        (1, "Kick Stones (The Boys)", 236_000, "6767652037"),
        (2, "Dobro", 165_000, "6767652039"),
    ]
    assert info.artwork_url.endswith("/600x600bb.jpg")


def test_bandcamp_page_gives_tracks_without_apple_ids():
    info = parse_music_album(BANDCAMP, "https://band.bandcamp.com/album/it-goes-on")
    assert info.release_date == "2026-08-21" and info.apple_music_id is None
    assert info.tracks[0].title == "Paper Chains" and info.tracks[0].duration_ms == 171_000
    assert info.artwork_url == "https://f4.bcbits.com/img/a0706145901_10.jpg"


def test_pages_without_a_track_list_are_ignored():
    assert parse_music_album("<html>nothing</html>", "https://x.test") is None
    empty = page({"@type": "MusicAlbum", "name": "A", "byArtist": {"name": "B"}, "tracks": []})
    assert parse_music_album(empty, "https://x.test") is None


def test_apple_comes_before_bandcamp_in_the_candidates():
    links = [
        "https://a.bandcamp.com/album/x",
        "https://music.apple.com/us/album/x/123456789",
        "https://news.test/a",
    ]
    assert structured_page_candidates(links) == [links[1], links[0]]


def test_research_urls_keep_press_and_drop_shops_archives_and_duplicates():
    links = [
        "http://www.nme.com/reviews/x",
        "https://nme.com/reviews/x/",  # same page again
        "https://web.archive.org/web/2026/https://nme.com/reviews/x",
        "https://music.apple.com/us/album/x/1",
        "https://westside.bandcamp.com/album/x",
        "https://www.metacritic.com/music/x",
        "https://genius.com/x",
        "https://pitchfork.com/reviews/albums/1/",
        "ftp://nope.test/x",
    ]
    assert pick_research_urls(links) == [
        "https://www.nme.com/reviews/x",
        "https://pitchfork.com/reviews/albums/1/",
    ]
    assert len(pick_research_urls([f"https://site{i}.test/a" for i in range(40)], limit=5)) == 5


def test_slugify():
    assert slugify("It Goes On Westside Cowboy") == "it-goes-on-westside-cowboy"


def test_skeleton_loads_as_an_album_with_no_claims_and_is_never_overwritten(tmp_path):
    info = parse_music_album(APPLE, "https://music.apple.com/us/album/it-goes-on/6767652034")
    folder = write_skeleton(tmp_path, "it-goes-on", info, ["https://nme.com/r"], note="test")
    bundle = load_album(tmp_path, "it-goes-on")
    assert bundle.album.apple_music_id == "6767652034"
    assert [(t.number, t.title, t.duration, t.apple_music_id) for t in bundle.tracks] == [
        (1, "Kick Stones (The Boys)", 236_000, "6767652037"),
        (2, "Dobro", 165_000, "6767652039"),
    ]
    assert bundle.album.claims == [] and all(not t.claims for t in bundle.tracks)
    assert "https://nme.com/r" in (folder / "research.yaml").read_text()
    with pytest.raises(FileExistsError):
        write_skeleton(tmp_path, "it-goes-on", info, [], note="again")


# ---- finding an album filed under its plain title ----------------------------------------------


class PlainTitleWeb(FakeWeb):
    def _wikipedia(self, request):
        if request.url.params.get("list") == "search":
            return self._json({"query": {"search": [{"title": "Sheep"}, {"title": "It Goes On"}]}})
        return super()._wikipedia(request)


def test_album_found_under_its_plain_title_when_it_is_about_the_artist(tmp_path, monkeypatch):
    monkeypatch.setitem(
        fakeweb.ARTICLES,
        "It Goes On",
        "It Goes On is the debut studio album by the English rock band Westside Cowboy.",
    )
    web = PlainTitleWeb()
    wiki = WikipediaCollector(
        Fetcher(ResearchCache(tmp_path), client=web.client, public_only=False, sleep=lambda s: None)
    )
    page_ = wiki.album_page("It Goes On", "Westside Cowboy")
    assert page_ is not None and page_.title == "It Goes On"


def test_a_same_named_article_about_something_else_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setitem(fakeweb.ARTICLES, "It Goes On", "It Goes On is a 1998 novel by a chef.")
    web = PlainTitleWeb()
    wiki = WikipediaCollector(
        Fetcher(ResearchCache(tmp_path), client=web.client, public_only=False, sleep=lambda s: None)
    )
    assert wiki.album_page("It Goes On", "Westside Cowboy") is None
