from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.deps import SessionDep
from app.models import Album, Annotation, Credit, Link, Moment, Track
from app.models.enums import Depth, EntityType, Phase
from app.schemas import (
    AlbumDetail,
    AlbumSummary,
    AnnotationOut,
    CreditOut,
    MomentOut,
    TrackDetail,
    TrackSummary,
)
from app.services import serialize as ser

router = APIRouter()


def _album(session: Session, slug: str) -> Album:
    album = session.scalar(
        select(Album).where(Album.slug == slug).options(selectinload(Album.tracks))
    )
    if album is None:
        raise HTTPException(404, f"No album '{slug}'")
    return album


def _credits(session: Session, **where) -> list[CreditOut]:
    rows = session.scalars(
        select(Credit).filter_by(**where).options(selectinload(Credit.person)).order_by(Credit.id)
    )
    return [CreditOut(person=c.person.name, role=c.role) for c in rows]


@router.get("/albums")
def list_albums(session: SessionDep) -> list[AlbumSummary]:
    """Curated album shelf."""
    albums = session.scalars(select(Album).options(selectinload(Album.artist)).order_by(Album.id))
    return [
        AlbumSummary(
            slug=a.slug,
            title=a.title,
            artist=a.artist.name,
            release_date=a.release_date,
            artwork_url=a.artwork_url,
        )
        for a in albums
    ]


@router.get("/albums/{slug}")
def get_album(slug: str, session: SessionDep, depth: Depth | None = None) -> AlbumDetail:
    """Album, tracklist, credits and the `before` and `after` claims (approved only)."""
    album = _album(session, slug)
    subjects = [(EntityType.artist, album.artist_id), (EntityType.album, album.id)]

    def claims(phase: Phase):
        return [
            ser.claim_out(c) for c in ser.public_claims(session, subjects, phase=phase, depth=depth)
        ]

    return AlbumDetail(
        slug=album.slug,
        title=album.title,
        artist=album.artist.name,
        release_date=album.release_date,
        artwork_url=album.artwork_url,
        apple_music_id=album.apple_music_id,
        tracks=[TrackSummary.model_validate(t, from_attributes=True) for t in album.tracks],
        credits=_credits(session, album_id=album.id),
        before=claims(Phase.before),
        after=claims(Phase.after),
    )


@router.get("/albums/{slug}/tracks/{number}")
def get_track(
    slug: str, number: int, session: SessionDep, depth: Depth | None = None, disc: int = 1
) -> TrackDetail:
    """Track with its `between` intro, `during` moments, annotations, credits and links."""
    album = _album(session, slug)
    track = session.scalar(
        select(Track).where(Track.album_id == album.id, Track.number == number, Track.disc == disc)
    )
    if track is None:
        raise HTTPException(404, f"No track {number} on '{slug}'")

    between = ser.public_claims(
        session, [(EntityType.track, track.id)], phase=Phase.between, depth=depth
    )
    moments = session.scalars(
        select(Moment)
        .where(Moment.track_id == track.id)
        .options(ser.selectinload(Moment.claim).options(ser.CLAIM_LOAD))
        .order_by(Moment.start_ms)
    )
    annotations = session.scalars(
        select(Annotation)
        .where(Annotation.track_id == track.id)
        .options(ser.selectinload(Annotation.claim).options(ser.CLAIM_LOAD))
        .order_by(Annotation.line_start)
    )
    links = session.scalars(
        select(Link)
        .where(Link.from_type == EntityType.track, Link.from_id == track.id)
        .options(ser.selectinload(Link.claim).options(ser.CLAIM_LOAD))
        .order_by(Link.id)
    )
    return TrackDetail(
        **TrackSummary.model_validate(track, from_attributes=True).model_dump(),
        isrc=track.isrc,
        album_slug=album.slug,
        between=ser.claim_out(between[0]) if between else None,
        claims=[
            ser.claim_out(c)
            for c in ser.public_claims(session, [(EntityType.track, track.id)], depth=depth)
        ],
        moments=[
            MomentOut(start_ms=m.start_ms, end_ms=m.end_ms, claim=ser.claim_out(m.claim))
            for m in moments
            if ser.is_public(m.claim, depth)
        ],
        annotations=[
            AnnotationOut(
                line_start=a.line_start, line_end=a.line_end, claim=ser.claim_out(a.claim)
            )
            for a in annotations
            if ser.is_public(a.claim, depth)
        ],
        credits=_credits(session, track_id=track.id),
        links=[out for link in links if (out := ser.link_out(link, depth))],
    )
