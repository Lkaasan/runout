"""API response and request models. These drive the generated TypeScript client."""

from datetime import date

from pydantic import BaseModel

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


class SourceOut(BaseModel):
    title: str
    url: str | None
    publisher: str | None
    author: str | None
    published_at: date | None
    kind: SourceKind
    tier: Tier


class ClaimSourceOut(BaseModel):
    source: SourceOut
    stance: Stance
    excerpt: str | None
    locator: str | None


class ClaimOut(BaseModel):
    id: int
    subject_type: EntityType
    subject_id: int
    type: ClaimType
    body: str
    body_long: str | None
    phase: Phase
    depth: Depth
    author: str | None
    confidence: float | None
    sources: list[ClaimSourceOut]


class AdminClaimOut(ClaimOut):
    key: str
    status: Status
    flagged: bool
    # Why this claim can't be approved right now (empty when it can).
    problems: list[str]


class CreditOut(BaseModel):
    person: str
    role: str


class AlbumSummary(BaseModel):
    slug: str
    title: str
    artist: str
    artist_slug: str
    release_date: date | None
    artwork_url: str | None


class ArtistSummary(BaseModel):
    slug: str
    name: str
    album_count: int
    # The cover of their newest album that has one, for a card.
    artwork_url: str | None


class ArtistDetail(BaseModel):
    slug: str
    name: str
    # Newest first.
    albums: list[AlbumSummary]
    # Approved claims about the artist as a whole.
    claims: list[ClaimOut]


class SearchResults(BaseModel):
    query: str
    artists: list[ArtistSummary]
    albums: list[AlbumSummary]


class TrackSummary(BaseModel):
    number: int
    disc: int
    title: str
    duration_ms: int | None
    apple_music_id: str | None


class AlbumDetail(AlbumSummary):
    apple_music_id: str | None
    tracks: list[TrackSummary]
    credits: list[CreditOut]
    before: list[ClaimOut]
    after: list[ClaimOut]


class LinkOut(BaseModel):
    relation: Relation
    from_type: EntityType
    from_id: int
    to_type: EntityType
    to_id: int | None
    target_title: str | None
    target_apple_music_id: str | None
    claim: ClaimOut | None


class MomentOut(BaseModel):
    start_ms: int
    end_ms: int | None
    claim: ClaimOut


class AnnotationOut(BaseModel):
    line_start: int
    line_end: int
    claim: ClaimOut


class TrackDetail(TrackSummary):
    isrc: str | None
    album_slug: str
    between: ClaimOut | None
    # Every approved claim about this track (the between intro and moment claims included).
    claims: list[ClaimOut]
    moments: list[MomentOut]
    annotations: list[AnnotationOut]
    credits: list[CreditOut]
    links: list[LinkOut]


class EntityDetail(BaseModel):
    type: EntityType
    id: int
    name: str
    claims: list[ClaimOut]
    links_out: list[LinkOut]
    links_in: list[LinkOut]


class ClaimPatch(BaseModel):
    status: Status | None = None
    body: str | None = None
    body_long: str | None = None
    author: str | None = None
    depth: Depth | None = None


class ImportResult(BaseModel):
    slug: str
    tracks: int
    sources: int
    claims: int
    approved: int
    draft: int
    warnings: list[str]
