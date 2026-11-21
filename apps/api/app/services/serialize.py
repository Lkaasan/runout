"""Turns ORM objects into API models, and holds the public (approved-only) claim queries."""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Claim, ClaimSource, Link
from app.models.enums import Depth, EntityType, Phase, Status
from app.schemas import (
    AdminClaimOut,
    ClaimOut,
    ClaimSourceOut,
    LinkOut,
    SourceOut,
)
from app.services import claim_rules

CLAIM_LOAD = selectinload(Claim.sources).selectinload(ClaimSource.source)


def claim_out(c: Claim) -> ClaimOut:
    return ClaimOut(
        id=c.id,
        subject_type=c.subject_type,
        subject_id=c.subject_id,
        type=c.type,
        body=c.body,
        body_long=c.body_long,
        phase=c.phase,
        depth=c.depth,
        author=c.author,
        confidence=c.confidence,
        sources=[
            ClaimSourceOut(
                source=SourceOut.model_validate(cs.source, from_attributes=True),
                stance=cs.stance,
                excerpt=cs.excerpt,
                locator=cs.locator,
            )
            for cs in c.sources
        ],
    )


def admin_claim_out(c: Claim) -> AdminClaimOut:
    return AdminClaimOut(
        **claim_out(c).model_dump(),
        key=c.key,
        status=c.status,
        flagged=c.flagged,
        problems=claim_rules.violations(c),
    )


def public_claims(
    session: Session,
    subjects: list[tuple[EntityType, int]],
    *,
    phase: Phase | None = None,
    depth: Depth | None = None,
) -> list[Claim]:
    """Approved claims on the given subjects. Rule 5: every public read goes through here."""
    claims: list[Claim] = []
    for subject_type, subject_id in subjects:
        stmt = (
            select(Claim)
            .where(Claim.subject_type == subject_type, Claim.subject_id == subject_id)
            .options(CLAIM_LOAD)
            .order_by(Claim.id)
        )
        if phase:
            stmt = stmt.where(Claim.phase == phase)
        if depth:
            stmt = stmt.where(Claim.depth == depth)
        claims += session.scalars(claim_rules.approved_only(stmt)).all()
    return claims


def is_public(claim: Claim | None, depth: Depth | None) -> bool:
    if claim is None:
        return True
    return claim.status == Status.approved and (depth is None or claim.depth == depth)


def link_out(link: Link, depth: Depth | None = None) -> LinkOut | None:
    """None when the link's claim is not public, so unreviewed links never leak."""
    if link.claim_id is not None and not is_public(link.claim, depth):
        return None
    return LinkOut(
        relation=link.relation,
        from_type=link.from_type,
        from_id=link.from_id,
        to_type=link.to_type,
        to_id=link.to_id,
        target_title=link.target_title,
        target_apple_music_id=link.target_apple_music_id,
        claim=claim_out(link.claim) if link.claim else None,
    )
