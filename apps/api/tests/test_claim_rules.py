import pytest
from sqlalchemy import select

from app.models import Claim, ClaimSource, Source
from app.models.enums import ClaimType, Stance, Status, Tier
from app.services import claim_rules
from app.services.claim_rules import ClaimRuleError


def make_claim(type_: ClaimType, *sources: tuple[Stance, Tier], author: str | None = None):
    claim = Claim(type=type_, status=Status.draft, author=author, body="x")
    for i, (stance, tier) in enumerate(sources):
        src = Source(key=f"s{i}", title="t", tier=tier)
        claim.sources.append(ClaimSource(source=src, stance=stance))
    return claim


# Rule 1
def test_fact_without_source_cannot_be_approved():
    claim = make_claim(ClaimType.fact)
    with pytest.raises(ClaimRuleError, match="supporting source"):
        claim_rules.approve(claim)
    assert claim.status == Status.draft


def test_fact_with_supporting_source_can_be_approved():
    claim = make_claim(ClaimType.fact, (Stance.supports, Tier.tertiary))
    claim_rules.approve(claim)
    assert claim.status == Status.approved


def test_fact_with_only_contradicting_source_cannot_be_approved():
    claim = make_claim(ClaimType.fact, (Stance.contradicts, Tier.primary))
    with pytest.raises(ClaimRuleError):
        claim_rules.approve(claim)


# Rule 2
def test_artist_intent_needs_primary_source():
    claim = make_claim(ClaimType.artist_intent, (Stance.supports, Tier.secondary))
    with pytest.raises(ClaimRuleError, match="primary"):
        claim_rules.approve(claim)


def test_artist_intent_with_primary_source_is_approved():
    claim = make_claim(ClaimType.artist_intent, (Stance.supports, Tier.primary))
    claim_rules.approve(claim)
    assert claim.status == Status.approved


def test_primary_source_must_support_not_contradict():
    claim = make_claim(
        ClaimType.artist_intent,
        (Stance.contradicts, Tier.primary),
        (Stance.supports, Tier.tertiary),
    )
    with pytest.raises(ClaimRuleError, match="primary"):
        claim_rules.approve(claim)


# Rule 3
def _contested():
    return make_claim(
        ClaimType.fact, (Stance.supports, Tier.primary), (Stance.contradicts, Tier.primary)
    )


def test_contradiction_flags_claim_and_blocks_auto_approval():
    claim = _contested()
    with pytest.raises(ClaimRuleError, match="human review"):
        claim_rules.approve(claim, auto=True)
    assert claim.flagged is True
    assert claim.status == Status.draft


def test_human_can_approve_flagged_claim():
    claim = _contested()
    claim_rules.approve(claim, auto=False)
    assert claim.status == Status.approved
    assert claim.flagged is True


# Rule 4
def test_interpretation_needs_no_source_but_needs_author():
    with pytest.raises(ClaimRuleError, match="author"):
        claim_rules.approve(make_claim(ClaimType.interpretation))
    claim = make_claim(ClaimType.interpretation, author="A Critic")
    claim_rules.approve(claim)
    assert claim.status == Status.approved


# Rule 5
def test_approved_only_filters_to_approved(session):
    for key, status in [("a", Status.approved), ("d", Status.draft), ("r", Status.rejected)]:
        session.add(
            Claim(
                key=key,
                subject_type="album",
                subject_id=1,
                type=ClaimType.trivia,
                body="b",
                phase="before",
                depth="listen",
                status=status,
            )
        )
    session.flush()
    rows = session.scalars(claim_rules.approved_only(select(Claim))).all()
    assert [c.key for c in rows] == ["a"]
