from pathlib import Path

from app.models.enums import ClaimType, SourceKind, Stance, Tier
from app.pipeline.models import Candidate, CandidateSource, Proposal
from app.pipeline.scoring import (
    Gold,
    GoldItem,
    load_gold,
    matches,
    proposal_from_seed,
    score,
)
from app.research import main as research_main
from app.services.seed_loader import load_album

CONTENT = Path(__file__).resolve().parents[3].parent / "content" / "albums"


def src(**kw) -> CandidateSource:
    base = dict(
        url="https://example.com/a",
        title="A source",
        kind=SourceKind.press,
        tier=Tier.secondary,
        excerpt="an excerpt",
    )
    return CandidateSource(**{**base, **kw})


def cand(id_="c", body="The pig floated over Battersea.", type_=ClaimType.fact, **kw) -> Candidate:
    return Candidate(id=id_, type=type_, body=body, sources=kw.pop("sources", [src()]), **kw)


GOLD = Gold(
    slug="x",
    non_primary_domains=["wikipedia.org"],
    items=[
        GoldItem(id="pig", kind="fact", keywords=[["pig"], ["battersea"]]),
        GoldItem(id="intent", kind="intent", keywords=[["sketch"]]),
        GoldItem(id="size", kind="conflict", keywords=[["pig"], ["30 feet", "12 m"]]),
    ],
)


def test_keyword_groups_need_one_hit_in_every_group():
    item = GoldItem(id="i", kind="fact", keywords=[["pig", "hog"], ["battersea"]])
    assert matches(item, cand(body="A hog over BATTERSEA"))
    assert not matches(item, cand(body="A pig over Brixton"))
    assert not matches(item, cand(body="Battersea power station"))


def test_empty_run_scores_zero_recall_and_no_errors():
    s = score(GOLD, Proposal(slug="x"))
    assert (s.facts_found, s.intent_found, s.conflicts_found) == (0, 0, 0)
    assert s.errors == 0
    assert set(s.missed) == {"pig", "intent", "size"}


def test_finds_fact_intent_and_conflict():
    conflict = cand(
        "size",
        body="The pig was about 30 feet long.",
        sources=[src(), src(url="https://example.com/b", stance=Stance.contradicts)],
    )
    s = score(
        GOLD,
        Proposal(
            slug="x",
            candidates=[
                cand(),
                cand("i", "A cartoon sketch of society.", ClaimType.artist_intent),
                conflict,
            ],
        ),
    )
    assert (s.facts_found, s.intent_found, s.conflicts_found) == (1, 1, 1)
    assert s.errors == 0 and not s.missed


def test_conflict_needs_both_stances():
    one_sided = cand("size", body="The pig was 30 feet long.")
    s = score(GOLD, Proposal(slug="x", candidates=[one_sided]))
    assert s.conflicts_found == 0 and "size" in s.missed


def test_false_primary_from_non_primary_domain():
    bad = cand(sources=[src(url="https://en.wikipedia.org/wiki/X", tier=Tier.primary)])
    ok = cand(
        "d", "Different text entirely.", sources=[src(url="https://band.com", tier=Tier.primary)]
    )
    s = score(GOLD, Proposal(slug="x", candidates=[bad, ok]))
    assert s.false_primary == 1


def test_artist_intent_approvable_only_with_primary_support():
    secondary = cand("i1", "A cartoon sketch.", ClaimType.artist_intent)
    primary = cand(
        "i2",
        "Another cartoon sketch remark.",
        ClaimType.artist_intent,
        sources=[src(url="https://band.example/interview", tier=Tier.primary)],
    )
    s = score(GOLD, Proposal(slug="x", candidates=[secondary, primary]))
    assert s.intent_wrongly_approvable == 1


def test_unsourced_and_missing_excerpt_are_flagged():
    no_sources = cand("a", "No sources here.", sources=[])
    no_excerpt = cand("b", "Source without a quote.", sources=[src(excerpt=None)])
    s = score(GOLD, Proposal(slug="x", candidates=[no_sources, no_excerpt]))
    assert s.unsourced == 2


def test_near_duplicates_are_counted():
    a = cand("a", "The pig floated over Battersea power station in 1976.")
    b = cand("b", "The pig floated over Battersea power station in 1976")
    s = score(GOLD, Proposal(slug="x", candidates=[a, b]))
    assert s.duplicates == 1


# ---- the real gold set ----------------------------------------------------------------------


def test_every_gold_item_matches_its_own_seed_claim():
    """The gold set must agree with the reviewed seed, or one of them is wrong."""
    gold = load_gold("animals")
    proposal = proposal_from_seed(load_album(CONTENT, "animals"))
    by_id = {c.id: c for c in proposal.candidates}
    for item in gold.items:
        assert item.seed_claim in by_id, f"{item.id}: no seed claim {item.seed_claim}"
        assert matches(item, by_id[item.seed_claim]), f"{item.id} does not match its seed claim"


def test_oracle_run_scores_full_recall_with_no_errors():
    gold = load_gold("animals")
    s = score(gold, proposal_from_seed(load_album(CONTENT, "animals")))
    assert (s.fact_recall, s.intent_recall, s.conflict_recall) == (1.0, 1.0, 1.0)
    assert s.errors == 0, s.report()


def test_empty_run_on_animals_scores_zero_recall():
    s = score(load_gold("animals"), Proposal(slug="animals"))
    assert s.fact_recall == 0 and s.intent_recall == 0 and s.conflict_recall == 0


def test_cli_scores_oracle_and_empty(capsys):
    assert research_main(["score", "animals", "--oracle"]) == 0
    assert "fact recall" in capsys.readouterr().out
    assert research_main(["score", "animals", "--empty"]) == 0
