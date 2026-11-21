"""Pydantic models for the seed files in content/albums/<slug>/."""

import re
from datetime import date
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from app.models.enums import ClaimType, Depth, EntityType, Phase, Relation, SourceKind, Stance, Tier

_TIME = re.compile(r"^(?:(\d+):)?([0-5]?\d):([0-5]\d)(?:\.(\d{1,3}))?$")


def parse_time_ms(value: object) -> int:
    """'2:14' -> 134000, '1:02:03' -> 3723000, '0:05.5' -> 5500."""
    if not isinstance(value, str):
        raise ValueError(f'timestamps must be quoted strings like "2:14", got {value!r}')
    m = _TIME.match(value.strip())
    if not m:
        raise ValueError(f'invalid timestamp {value!r}, expected "M:SS" or "H:MM:SS"')
    hours, minutes, seconds, frac = m.groups()
    ms = ((int(hours or 0) * 60 + int(minutes)) * 60 + int(seconds)) * 1000
    return ms + (int((frac or "0").ljust(3, "0")) if frac else 0)


Timestamp = Annotated[int, BeforeValidator(parse_time_ms)]


def _as_str(value: object) -> object:
    # Unquoted values like 12:40 or 123 are ints in YAML; locators are free text.
    return str(value) if isinstance(value, int | float) and not isinstance(value, bool) else value


Text = Annotated[str, BeforeValidator(_as_str)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceSeed(Strict):
    id: str
    kind: SourceKind
    title: str
    url: str | None = None
    publisher: str | None = None
    author: str | None = None
    published_at: date | None = None
    tier: Tier


class SourcesFile(Strict):
    sources: list[SourceSeed]


class ClaimSourceSeed(Strict):
    ref: str
    stance: Stance = Stance.supports
    excerpt: str | None = None
    locator: Text | None = None


class ClaimSeed(Strict):
    id: str
    type: ClaimType
    depth: Depth = Depth.listen
    # Optional on tracks (derived from how the claim is used); required for album-level claims.
    phase: Phase | None = None
    # Album file only: attach the claim to the artist instead of the album.
    subject: EntityType | None = None
    body: str
    body_long: str | None = None
    author: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    sources: list[ClaimSourceSeed] = []
    reviewed: bool = False


class ClaimRef(Strict):
    claim: str


class MomentSeed(Strict):
    at: Timestamp
    until: Timestamp | None = None
    claim: str

    @model_validator(mode="after")
    def _ordered(self):
        if self.until is not None and self.until <= self.at:
            raise ValueError("'until' must be after 'at'")
        return self


class AnnotationSeed(Strict):
    lines: tuple[int, int]
    claim: str

    @model_validator(mode="after")
    def _ordered(self):
        if self.lines[0] < 0 or self.lines[1] < self.lines[0]:
            raise ValueError("'lines' must be [first, last] with 0 <= first <= last")
        return self


class LinkTarget(Strict):
    type: EntityType
    apple_music_id: str | None = None
    title: str | None = None

    @model_validator(mode="after")
    def _identifiable(self):
        if not (self.apple_music_id or self.title):
            raise ValueError("a link target needs an apple_music_id or a title")
        return self


class LinkSeed(Strict):
    relation: Relation
    to: LinkTarget
    claim: str | None = None


class CreditSeed(Strict):
    person: str
    role: str
    musicbrainz_id: str | None = None


class ArtistSeed(Strict):
    name: str
    apple_music_id: str | None = None
    musicbrainz_id: str | None = None


class AlbumSeed(Strict):
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    title: str
    artist: ArtistSeed
    release_date: date | None = None
    apple_music_id: str | None = None
    musicbrainz_release_id: str | None = None
    artwork_url: str | None = None
    credits: list[CreditSeed] = []
    claims: list[ClaimSeed] = []
    links: list[LinkSeed] = []


class TrackSeed(Strict):
    number: int = Field(ge=1)
    disc: int = Field(default=1, ge=1)
    title: str
    duration: Timestamp | None = None
    apple_music_id: str | None = None
    isrc: str | None = None
    between: ClaimRef | None = None
    moments: list[MomentSeed] = []
    annotations: list[AnnotationSeed] = []
    links: list[LinkSeed] = []
    credits: list[CreditSeed] = []
    claims: list[ClaimSeed] = []
