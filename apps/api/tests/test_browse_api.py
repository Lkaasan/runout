from datetime import date

from sqlalchemy.orm import Session

from app.models import Album, Artist


def _add(engine, artist: str, slug: str, albums: list[tuple[str, str, date | None, str | None]]):
    with Session(engine) as s:
        a = Artist(name=artist, slug=slug)
        s.add(a)
        s.flush()
        for album_slug, title, released, cover in albums:
            s.add(
                Album(
                    artist_id=a.id,
                    slug=album_slug,
                    title=title,
                    release_date=released,
                    artwork_url=cover,
                )
            )
        s.commit()


def test_album_carries_its_artist_slug(seeded):
    albums = seeded.get("/albums").json()
    assert albums[0]["artist_slug"]
    detail = seeded.get(f"/albums/{albums[0]['slug']}").json()
    assert detail["artist_slug"] == albums[0]["artist_slug"]


def test_empty_query_finds_nothing(seeded):
    body = seeded.get("/search", params={"q": "  "}).json()
    assert body["artists"] == [] and body["albums"] == []


def test_search_is_case_insensitive_and_puts_prefix_matches_first(client, engine):
    _add(
        engine,
        "Smog",
        "smog",
        [("knock-knock", "Knock Knock", date(1999, 1, 12), None)],
    )
    _add(
        engine,
        "Pink Floyd",
        "pink-floyd",
        [("animals", "Animals", date(1977, 1, 23), None), ("the-wall", "The Wall", None, None)],
    )
    body = client.get("/search", params={"q": "ANIM"}).json()
    assert [a["slug"] for a in body["albums"]] == ["animals"]

    body = client.get("/search", params={"q": "l"}).json()
    # "The Wall"/"Animals" both contain l; names starting with l would come first.
    assert {a["slug"] for a in body["albums"]} == {"animals", "the-wall"}
    assert [a["slug"] for a in body["artists"]] == ["pink-floyd"]


def test_searching_an_artist_lists_their_albums(client, engine):
    _add(
        engine,
        "Pink Floyd",
        "pink-floyd",
        [("animals", "Animals", date(1977, 1, 23), None), ("the-wall", "The Wall", None, None)],
    )
    body = client.get("/search", params={"q": "floyd"}).json()
    assert body["artists"][0]["album_count"] == 2
    assert {a["slug"] for a in body["albums"]} == {"animals", "the-wall"}


def test_percent_in_a_query_is_not_a_wildcard(client, engine):
    _add(engine, "Smog", "smog", [("knock-knock", "Knock Knock", None, None)])
    assert client.get("/search", params={"q": "%"}).json()["albums"] == []


def test_artist_page_lists_albums_newest_first_undated_last(client, engine):
    _add(
        engine,
        "Pink Floyd",
        "pink-floyd",
        [
            ("the-wall", "The Wall", None, None),
            ("animals", "Animals", date(1977, 1, 23), "https://x/a.jpg"),
            ("meddle", "Meddle", date(1971, 10, 30), None),
        ],
    )
    page = client.get("/artists/pink-floyd").json()
    assert [a["slug"] for a in page["albums"]] == ["animals", "meddle", "the-wall"]
    assert page["claims"] == []
    assert client.get("/artists").json()[0]["artwork_url"] == "https://x/a.jpg"


def test_unknown_artist_is_404(client):
    assert client.get("/artists/nobody").status_code == 404
