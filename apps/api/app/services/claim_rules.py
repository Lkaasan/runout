"""The claim rules. Everything that changes a claim's status goes through here.

1. A `fact` claim cannot be approved without at least one supporting source.
2. An `artist_intent` claim needs at least one supporting source of tier `primary`.
3. A claim with any contradicting source is flagged for review and cannot be auto-approved.
4. `interpretation` claims may have no source, but are always credited to their author.
5. Public endpoints only ever return `approved` claims (see `approved_only`).
"""

from sqlalchemy import Select

from app.models import Claim
from app.models.enums import ClaimType, Stance, Status, Tier


class ClaimRuleError(Exception):
    def __init__(self, violations: list[str]):
        self.violations = violations
        super().__init__("; ".join(violations))


def has_contradiction(claim: Claim) -> bool:
    return any(cs.stance == Stance.contradicts for cs in claim.sources)


def refresh_flag(claim: Claim) -> None:
    """Rule 3: any contradicting source flags the claim for human review."""
    claim.flagged = has_contradiction(claim)


def violations(claim: Claim, *, auto: bool = False) -> list[str]:
    """Reasons this claim may not be approved. `auto` means approval without a human decision."""
    supporting = [cs for cs in claim.sources if cs.stance == Stance.supports]
    found: list[str] = []

    if claim.type == ClaimType.fact and not supporting:
        found.append("A fact needs at least one supporting source.")
    if claim.type == ClaimType.artist_intent and not any(
        cs.source.tier == Tier.primary for cs in supporting
    ):
        found.append("Artist intent needs at least one supporting primary source.")
    if claim.type == ClaimType.interpretation and not (claim.author or "").strip():
        found.append("An interpretation must be credited to its author.")
    if auto and has_contradiction(claim):
        found.append("A claim with a contradicting source needs human review.")
    return found


def approve(claim: Claim, *, auto: bool = False) -> None:
    refresh_flag(claim)
    problems = violations(claim, auto=auto)
    if problems:
        raise ClaimRuleError(problems)
    claim.status = Status.approved


def approved_only(stmt: Select) -> Select:
    """Rule 5: every public claim query must pass through this."""
    return stmt.where(Claim.status == Status.approved)
