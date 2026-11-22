"""The shapes the information finder passes around.

A `Candidate` is one proposed claim with the evidence behind it. It mirrors the seed format
(`app/services/seed_schema.py`) closely enough to render straight into seed YAML, but carries
extras the seed has no room for: the source URL, an excerpt and the stance of each source.
Nothing here is trusted: candidates are only proposals until the code checks and a human review.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ClaimType, Depth, Phase, SourceKind, Stance, Tier


class CandidateSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str | None = None
    title: str
    kind: SourceKind
    # What the finder believes. Code may lower it (never raise it) based on the domain.
    tier: Tier
    stance: Stance = Stance.supports
    # Short quote from the fetched page. Must be verifiable against the cached page text.
    excerpt: str | None = Field(default=None, max_length=400)
    locator: str | None = None


class Candidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    subject: Literal["artist", "album", "track"] = "album"
    # Set when subject is "track".
    track_number: int | None = Field(default=None, ge=1)
    type: ClaimType
    depth: Depth = Depth.listen
    phase: Phase | None = None
    body: str
    body_long: str | None = None
    author: str | None = None
    sources: list[CandidateSource] = []


class Proposal(BaseModel):
    """Everything one run proposes for one album."""

    model_config = ConfigDict(extra="forbid")

    slug: str
    candidates: list[Candidate] = []


class Page(BaseModel):
    """Text the finder fetched, stored so every later stage reads the same words.

    `text` is what excerpts are verified against, so it is stored exactly as collected.
    `meta` holds structured extras (ids, outgoing links) that are not part of the text.
    """

    model_config = ConfigDict(extra="forbid")

    url: str
    title: str
    kind: Literal["wikipedia", "musicbrainz"]
    fetched_at: datetime
    text: str
    meta: dict[str, Any] = {}
