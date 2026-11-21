from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, str_enum
from app.models.enums import (
    ClaimType,
    Depth,
    EntityType,
    Phase,
    Relation,
    SourceKind,
    Stance,
    Status,
    Tier,
)


class Artist(Base):
    __tablename__ = "artist"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    apple_music_id: Mapped[str | None] = mapped_column(String(64))
    musicbrainz_id: Mapped[str | None] = mapped_column(String(64))


class Album(Base):
    __tablename__ = "album"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(128), unique=True)
    artist_id: Mapped[int] = mapped_column(ForeignKey("artist.id"))
    title: Mapped[str] = mapped_column(String(255))
    release_date: Mapped[date | None] = mapped_column(Date)
    apple_music_id: Mapped[str | None] = mapped_column(String(64))
    musicbrainz_release_id: Mapped[str | None] = mapped_column(String(64))
    artwork_url: Mapped[str | None] = mapped_column(String(1024))

    artist: Mapped[Artist] = relationship()
    tracks: Mapped[list[Track]] = relationship(
        back_populates="album", order_by="(Track.disc, Track.number)"
    )


class Track(Base):
    __tablename__ = "track"
    __table_args__ = (UniqueConstraint("album_id", "disc", "number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    album_id: Mapped[int] = mapped_column(ForeignKey("album.id"))
    disc: Mapped[int] = mapped_column(Integer, default=1)
    number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(255))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    # Match to Apple Music by ID, fall back to ISRC.
    apple_music_id: Mapped[str | None] = mapped_column(String(64))
    isrc: Mapped[str | None] = mapped_column(String(16))

    album: Mapped[Album] = relationship(back_populates="tracks")


class Person(Base):
    """Producers, engineers, session players."""

    __tablename__ = "person"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    musicbrainz_id: Mapped[str | None] = mapped_column(String(64))


class Credit(Base):
    __tablename__ = "credit"
    __table_args__ = (
        CheckConstraint(
            "(album_id IS NOT NULL) <> (track_id IS NOT NULL)", name="exactly_one_target"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"))
    album_id: Mapped[int | None] = mapped_column(ForeignKey("album.id"))
    track_id: Mapped[int | None] = mapped_column(ForeignKey("track.id"))
    role: Mapped[str] = mapped_column(String(128))

    person: Mapped[Person] = relationship()


class Source(Base):
    __tablename__ = "source"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Stable seed id: "<album-slug>/<source-id>".
    key: Mapped[str] = mapped_column(String(255), unique=True)
    kind: Mapped[SourceKind] = mapped_column(str_enum(SourceKind))
    title: Mapped[str] = mapped_column(String(512))
    url: Mapped[str | None] = mapped_column(String(2048))
    publisher: Mapped[str | None] = mapped_column(String(255))
    author: Mapped[str | None] = mapped_column(String(255))
    published_at: Mapped[date | None] = mapped_column(Date)
    tier: Mapped[Tier] = mapped_column(str_enum(Tier))


class Claim(Base):
    """Everything a user reads is a claim on a subject, backed by sources, placed in a phase."""

    __tablename__ = "claim"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Stable seed id: "<album-slug>/<claim-id>".
    key: Mapped[str] = mapped_column(String(255), unique=True)
    # Polymorphic reference to artist/album/track/person; deliberately not a foreign key.
    subject_type: Mapped[EntityType] = mapped_column(str_enum(EntityType))
    subject_id: Mapped[int] = mapped_column(Integer)
    type: Mapped[ClaimType] = mapped_column(str_enum(ClaimType))
    body: Mapped[str] = mapped_column(Text)
    body_long: Mapped[str | None] = mapped_column(Text)
    phase: Mapped[Phase] = mapped_column(str_enum(Phase))
    depth: Mapped[Depth] = mapped_column(str_enum(Depth), default=Depth.listen)
    status: Mapped[Status] = mapped_column(str_enum(Status), default=Status.draft)
    confidence: Mapped[float | None] = mapped_column(Float)
    # Who is speaking; interpretations are always credited to their author.
    author: Mapped[str | None] = mapped_column(String(255))
    # True when any source contradicts the claim: needs a human decision.
    flagged: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    sources: Mapped[list[ClaimSource]] = relationship(
        back_populates="claim", cascade="all, delete-orphan"
    )


class ClaimSource(Base):
    __tablename__ = "claim_source"

    id: Mapped[int] = mapped_column(primary_key=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claim.id", ondelete="CASCADE"))
    source_id: Mapped[int] = mapped_column(ForeignKey("source.id"))
    stance: Mapped[Stance] = mapped_column(str_enum(Stance), default=Stance.supports)
    excerpt: Mapped[str | None] = mapped_column(Text)
    # Page or video timestamp.
    locator: Mapped[str | None] = mapped_column(String(64))

    claim: Mapped[Claim] = relationship(back_populates="sources")
    source: Mapped[Source] = relationship()


class Moment(Base):
    """A "listen for this" card shown at a timestamp."""

    __tablename__ = "moment"

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("track.id"))
    start_ms: Mapped[int] = mapped_column(Integer)
    end_ms: Mapped[int | None] = mapped_column(Integer)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claim.id"))

    claim: Mapped[Claim] = relationship()


class Annotation(Base):
    """Anchors a claim to lyric line indexes. Lyric text itself is never stored."""

    __tablename__ = "annotation"

    id: Mapped[int] = mapped_column(primary_key=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("track.id"))
    line_start: Mapped[int] = mapped_column(Integer)
    line_end: Mapped[int] = mapped_column(Integer)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claim.id"))

    claim: Mapped[Claim] = relationship()


class Link(Base):
    """An edge in the deep-dive graph.

    The target may not exist in our catalogue (e.g. a sampled original), so it is described by
    `target_apple_music_id` and `target_title` when `to_id` is null.
    """

    __tablename__ = "link"

    id: Mapped[int] = mapped_column(primary_key=True)
    from_type: Mapped[EntityType] = mapped_column(str_enum(EntityType))
    from_id: Mapped[int] = mapped_column(Integer)
    to_type: Mapped[EntityType] = mapped_column(str_enum(EntityType))
    to_id: Mapped[int | None] = mapped_column(Integer)
    relation: Mapped[Relation] = mapped_column(str_enum(Relation))
    claim_id: Mapped[int | None] = mapped_column(ForeignKey("claim.id"))
    target_apple_music_id: Mapped[str | None] = mapped_column(String(64))
    target_title: Mapped[str | None] = mapped_column(String(255))
