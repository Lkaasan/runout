"""Reading the library for the homepage, artist pages and search. Public data only."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Album, Artist
from app.models.enums import EntityType
from app.schemas import AlbumSummary, ArtistDetail, ArtistSummary, SearchResults
from app.services import serialize as ser


def album_summary(a: Album) -> AlbumSummary:
    return AlbumSummary(
        slug=a.slug,
        title=a.title,
        artist=a.artist.name,
        artist_slug=a.artist.slug,
        release_date=a.release_date,
        artwork_url=a.artwork_url,
    )


def _newest_first(albums: list[Album]) -> list[Album]:
    # Albums with no date go last; title keeps the order stable.
    dated = sorted(
        (a for a in albums if a.release_date), key=lambda a: (a.release_date, a.title), reverse=True
    )
    undated = sorted((a for a in albums if not a.release_date), key=lambda a: a.title)
    return dated + undated


def _artist_summary(artist: Artist, albums: list[Album]) -> ArtistSummary:
    cover = next((a.artwork_url for a in _newest_first(albums) if a.artwork_url), None)
    return ArtistSummary(
        slug=artist.slug, name=artist.name, album_count=len(albums), artwork_url=cover
    )


def _albums_by_artist(session: Session) -> dict[int, list[Album]]:
    by_artist: dict[int, list[Album]] = {}
    for a in session.scalars(select(Album)):
        by_artist.setdefault(a.artist_id, []).append(a)
    return by_artist


def list_artists(session: Session) -> list[ArtistSummary]:
    by_artist = _albums_by_artist(session)
    artists = session.scalars(select(Artist).order_by(func.lower(Artist.name)))
    # An artist with no album has no page worth visiting.
    return [_artist_summary(x, by_artist[x.id]) for x in artists if x.id in by_artist]


def get_artist(session: Session, slug: str) -> ArtistDetail | None:
    artist = session.scalar(select(Artist).where(Artist.slug == slug))
    if artist is None:
        return None
    albums = session.scalars(
        select(Album).where(Album.artist_id == artist.id).options(selectinload(Album.artist))
    ).all()
    claims = ser.public_claims(session, [(EntityType.artist, artist.id)])
    return ArtistDetail(
        slug=artist.slug,
        name=artist.name,
        albums=[album_summary(a) for a in _newest_first(list(albums))],
        claims=[ser.claim_out(c) for c in claims],
    )


def _like(text: str) -> str:
    """Escape LIKE wildcards so a search for '100%' means exactly that."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search(session: Session, query: str, limit: int = 8) -> SearchResults:
    """Artists and albums whose name contains the query (case-insensitive).

    Names that start with the query come before ones that merely contain it. Albums by a
    matching artist are included, so searching an artist also lists their records.
    """
    q = query.strip()
    if not q:
        return SearchResults(query=q, artists=[], albums=[])
    low_q = q.lower()
    contains = f"%{_like(low_q)}%"

    def rank(name: str) -> tuple[int, str]:
        low = name.lower()
        return (0 if low.startswith(low_q) else 1, low)

    artists = session.scalars(
        select(Artist).where(func.lower(Artist.name).like(contains, escape="\\"))
    ).all()
    albums = session.scalars(
        select(Album)
        .join(Artist)
        .where(
            func.lower(Album.title).like(contains, escape="\\")
            | func.lower(Artist.name).like(contains, escape="\\")
        )
        .options(selectinload(Album.artist))
    ).all()

    by_artist = _albums_by_artist(session)
    matched = [x for x in sorted(artists, key=lambda x: rank(x.name)) if x.id in by_artist]
    ordered = sorted(albums, key=lambda a: rank(a.title))
    return SearchResults(
        query=q,
        artists=[_artist_summary(x, by_artist[x.id]) for x in matched[:limit]],
        albums=[album_summary(a) for a in ordered[:limit]],
    )
