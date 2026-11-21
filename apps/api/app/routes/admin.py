from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.config import settings
from app.deps import AdminDep, SessionDep
from app.models import Claim
from app.models.enums import Status
from app.schemas import AdminClaimOut, ClaimPatch, ImportResult
from app.services import claim_rules
from app.services import serialize as ser
from app.services.importer import import_album
from app.services.seed_loader import SeedValidationError, load_album

router = APIRouter(prefix="/admin", dependencies=[AdminDep])


@router.get("/claims")
def review_queue(session: SessionDep, status: Status = Status.draft) -> list[AdminClaimOut]:
    """Claims awaiting review, with sources and anything blocking approval. Flagged first."""
    claims = session.scalars(
        select(Claim).where(Claim.status == status).options(ser.CLAIM_LOAD).order_by(Claim.id)
    ).all()
    claims = sorted(claims, key=lambda c: not c.flagged)
    return [ser.admin_claim_out(c) for c in claims]


@router.patch("/claims/{claim_id}")
def update_claim(claim_id: int, patch: ClaimPatch, session: SessionDep) -> AdminClaimOut:
    """Approve, reject or edit. 422 (with the reasons) if a claim rule fails; nothing is saved."""
    claim = session.scalar(select(Claim).where(Claim.id == claim_id).options(ser.CLAIM_LOAD))
    if claim is None:
        raise HTTPException(404, f"No claim {claim_id}")

    for field in ("body", "body_long", "author", "depth"):
        value = getattr(patch, field)
        if value is not None:
            setattr(claim, field, value)

    if patch.status == Status.approved:
        try:
            claim_rules.approve(claim)
        except claim_rules.ClaimRuleError as exc:
            session.rollback()
            raise HTTPException(
                422, detail={"message": "Claim cannot be approved", "violations": exc.violations}
            ) from exc
    elif patch.status is not None:
        claim.status = patch.status

    session.commit()
    return ser.admin_claim_out(claim)


@router.post("/import/{slug}")
def import_seed(slug: str, session: SessionDep) -> ImportResult:
    """Re-import an album's seed files."""
    try:
        bundle = load_album(settings.content_dir, slug)
    except SeedValidationError as exc:
        raise HTTPException(
            422,
            detail={
                "message": "Seed files are invalid",
                "violations": [str(e) for e in exc.errors],
            },
        ) from exc
    report = import_album(session, bundle)
    session.commit()
    return ImportResult(**{k: getattr(report, k) for k in ImportResult.model_fields})
