"""Upserts a validated album bundle into the database. Safe to run repeatedly.

Seed files own content (bodies, sources, moments, links, credits). Review decisions made in the
admin view are kept: an existing claim is only reset to draft when its text changes, or when it no
longer satisfies the claim rules.
"""

from dataclasses import dataclass, field

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import (
    Album,
    Annotation,
    Artist,
    Claim,
    ClaimSource,
    Credit,
    Link,
    Moment,
    Person,
    Source,
    Track,
)
from app.models.enums import EntityType, Status
from app.services import claim_rules
from app.services.seed_loader import AlbumBundle
from app.services.seed_schema import ClaimSeed, CreditSeed, LinkSeed


@dataclass
class ImportReport:
    slug: str
    tracks: int = 0
    sources: int = 0
    claims: int = 0
    approved: int = 0
    draft: int = 0
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"Imported '{self.slug}': {self.tracks} tracks, {self.sources} sources, "
            f"{self.claims} claims ({self.approved} approved, {self.draft} draft)."
        ]
        lines += [f"  warning: {w}" for w in self.warnings]
        return "\n".join(lines)


def _get_or_create[T](session: Session, model: type[T], **where) -> T:
    obj = session.scalar(select(model).filter_by(**where))
    if obj is None:
        obj = model(**where)
        session.add(obj)
    return obj


def import_album(session: Session, bundle: AlbumBundle) -> ImportReport:
    seed = bundle.album
    slug = seed.slug
    report = ImportReport(slug=slug)

    artist = _get_or_create(session, Artist, name=seed.artist.name)
    artist.apple_music_id = seed.artist.apple_music_id
    artist.musicbrainz_id = seed.artist.musicbrainz_id

    album = _get_or_create(session, Album, slug=slug)
    album.artist = artist
    album.title = seed.title
    album.release_date = seed.release_date
    album.apple_music_id = seed.apple_music_id
    album.musicbrainz_release_id = seed.musicbrainz_release_id
    album.artwork_url = seed.artwork_url
    session.flush()

    tracks: dict[int, Track] = {}
    for ts in bundle.tracks:
        track = session.scalar(
            select(Track).filter_by(album_id=album.id, disc=ts.disc, number=ts.number)
        )
        if track is None:
            track = Track(album_id=album.id, disc=ts.disc, number=ts.number, title=ts.title)
            session.add(track)
        track.title = ts.title
        track.duration_ms = ts.duration
        track.apple_music_id = ts.apple_music_id
        track.isrc = ts.isrc
        tracks[id(ts)] = track
    session.flush()
    report.tracks = len(tracks)

    sources: dict[str, Source] = {}
    for ss in bundle.sources:
        source = _get_or_create(session, Source, key=f"{slug}/{ss.id}")
        source.kind, source.title, source.url = ss.kind, ss.title, ss.url
        source.publisher, source.author = ss.publisher, ss.author
        source.published_at, source.tier = ss.published_at, ss.tier
        sources[ss.id] = source
    session.flush()
    report.sources = len(sources)

    # Claims
    claims: dict[str, Claim] = {}

    def upsert_claim(cs: ClaimSeed, subject_type: EntityType, subject_id: int) -> None:
        key = f"{slug}/{cs.id}"
        claim = session.scalar(select(Claim).filter_by(key=key))
        is_new = claim is None
        if claim is None:
            claim = Claim(key=key, status=Status.draft)
            session.add(claim)
        text_changed = not is_new and (claim.body, claim.body_long) != (cs.body, cs.body_long)

        claim.subject_type, claim.subject_id = subject_type, subject_id
        claim.type, claim.depth, claim.phase = cs.type, cs.depth, bundle.phases[cs.id]
        claim.body, claim.body_long = cs.body, cs.body_long
        claim.author, claim.confidence = cs.author, cs.confidence
        claim.sources = [
            ClaimSource(
                source=sources[r.ref], stance=r.stance, excerpt=r.excerpt, locator=r.locator
            )
            for r in cs.sources
        ]
        claim_rules.refresh_flag(claim)

        if text_changed:
            claim.status = Status.draft
        if cs.reviewed:
            try:
                claim_rules.approve(claim, auto=True)
            except claim_rules.ClaimRuleError as exc:
                claim.status = Status.draft
                report.warnings.append(f"{key} is marked reviewed but stays draft: {exc}")
        elif claim.status == Status.approved and (problems := claim_rules.violations(claim)):
            claim.status = Status.draft
            report.warnings.append(f"{key} was approved but now fails the rules: {problems}")
        claims[cs.id] = claim

    for cs in seed.claims:
        subject = cs.subject or EntityType.album
        if subject == EntityType.artist:
            upsert_claim(cs, EntityType.artist, artist.id)
        elif subject == EntityType.album:
            upsert_claim(cs, EntityType.album, album.id)
        else:
            raise ValueError(f"album-level claim '{cs.id}': subject must be artist or album")
    for ts in bundle.tracks:
        for cs in ts.claims:
            upsert_claim(cs, EntityType.track, tracks[id(ts)].id)
    session.flush()

    # Children that the seed fully owns are replaced wholesale.
    track_ids = [t.id for t in tracks.values()]
    session.execute(delete(Moment).where(Moment.track_id.in_(track_ids)))
    session.execute(delete(Annotation).where(Annotation.track_id.in_(track_ids)))
    session.execute(delete(Credit).where(Credit.track_id.in_(track_ids)))
    session.execute(delete(Credit).where(Credit.album_id == album.id))
    session.execute(
        delete(Link).where(
            ((Link.from_type == EntityType.album) & (Link.from_id == album.id))
            | ((Link.from_type == EntityType.track) & Link.from_id.in_(track_ids))
        )
    )

    def add_credits(items: list[CreditSeed], *, album_id=None, track_id=None) -> None:
        for c in items:
            person = _get_or_create(session, Person, name=c.person)
            if c.musicbrainz_id:
                person.musicbrainz_id = c.musicbrainz_id
            session.add(Credit(person=person, role=c.role, album_id=album_id, track_id=track_id))

    def add_links(items: list[LinkSeed], from_type: EntityType, from_id: int) -> None:
        for link in items:
            session.add(
                Link(
                    from_type=from_type,
                    from_id=from_id,
                    to_type=link.to.type,
                    relation=link.relation,
                    claim_id=claims[link.claim].id if link.claim else None,
                    target_apple_music_id=link.to.apple_music_id,
                    target_title=link.to.title,
                )
            )

    add_credits(seed.credits, album_id=album.id)
    add_links(seed.links, EntityType.album, album.id)
    for ts in bundle.tracks:
        track = tracks[id(ts)]
        add_credits(ts.credits, track_id=track.id)
        add_links(ts.links, EntityType.track, track.id)
        for m in ts.moments:
            session.add(
                Moment(
                    track_id=track.id, start_ms=m.at, end_ms=m.until, claim_id=claims[m.claim].id
                )
            )
        for a in ts.annotations:
            session.add(
                Annotation(
                    track_id=track.id,
                    line_start=a.lines[0],
                    line_end=a.lines[1],
                    claim_id=claims[a.claim].id,
                )
            )
    session.flush()

    report.claims = len(claims)
    report.approved = sum(c.status == Status.approved for c in claims.values())
    report.draft = report.claims - report.approved
    return report
