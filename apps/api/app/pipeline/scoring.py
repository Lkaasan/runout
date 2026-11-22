"""Scores a proposal against a hand-checked gold set.

This is how the finder is "trained": every change to a prompt, tool or rule is run through the
same gold set and kept only if the numbers improve. The matching here is deliberately simple and
deterministic (keyword groups), so a score is cheap, repeatable and needs no model.

Gold file format (see evals/gold/animals.yaml):

    slug: animals
    non_primary_domains: [wikipedia.org, ...]   # a primary tier from these is always wrong
    items:
      - id: dogs-intro
        kind: fact | intent | conflict
        keywords: [[any, of], [any, of]]         # every inner list needs one hit in the body
        seed_claim: dogs-intro                   # optional: claim in the reviewed seed
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import yaml
from pydantic import BaseModel, ConfigDict

from app.models import Claim, ClaimSource, Source
from app.models.enums import ClaimType, Stance, Tier
from app.pipeline.models import Candidate, CandidateSource, Proposal
from app.services import claim_rules
from app.services.seed_loader import AlbumBundle

GOLD_DIR = Path(__file__).resolve().parents[2] / "evals" / "gold"


class GoldItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: str  # "fact", "intent" or "conflict"
    keywords: list[list[str]]
    seed_claim: str | None = None


class Gold(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str
    non_primary_domains: list[str] = []
    items: list[GoldItem]


def load_gold(slug: str, gold_dir: Path = GOLD_DIR) -> Gold:
    return Gold.model_validate(yaml.safe_load((gold_dir / f"{slug}.yaml").read_text("utf-8")))


# ---- matching ------------------------------------------------------------------------------


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().replace("’", "'")).strip()


def matches(item: GoldItem, candidate: Candidate) -> bool:
    text = _norm(candidate.body + " " + (candidate.body_long or ""))
    return all(any(_norm(k) in text for k in group) for group in item.keywords)


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9']+", _norm(text)))


def _similar(a: str, b: str) -> float:
    wa, wb = _words(a), _words(b)
    return len(wa & wb) / len(wa | wb) if wa | wb else 0.0


def _domain(url: str | None) -> str:
    return (urlparse(url).hostname or "").removeprefix("www.") if url else ""


def approvable(candidate: Candidate) -> bool:
    """Would the importer approve this on its own (reviewed: true)? Uses the real claim rules."""
    claim = Claim(
        type=candidate.type, author=candidate.author, body=candidate.body, key=candidate.id
    )
    for i, s in enumerate(candidate.sources):
        source = Source(key=f"s{i}", title=s.title, kind=s.kind, tier=s.tier)
        claim.sources.append(ClaimSource(source=source, stance=s.stance))
    return not claim_rules.violations(claim, auto=True)


# ---- scoring -------------------------------------------------------------------------------


@dataclass
class Score:
    slug: str
    candidates: int = 0
    facts_found: int = 0
    facts_total: int = 0
    intent_found: int = 0
    intent_total: int = 0
    conflicts_found: int = 0
    conflicts_total: int = 0
    # Wrong in a way a human reviewer should never have to catch:
    false_primary: int = 0  # tier "primary" on a source from a known non-primary domain
    intent_wrongly_approvable: int = 0  # artist intent that would pass without a primary source
    unsourced: int = 0  # candidate without a source or without an excerpt
    duplicates: int = 0
    missed: list[str] = field(default_factory=list)

    @property
    def fact_recall(self) -> float:
        return self.facts_found / self.facts_total if self.facts_total else 1.0

    @property
    def intent_recall(self) -> float:
        return self.intent_found / self.intent_total if self.intent_total else 1.0

    @property
    def conflict_recall(self) -> float:
        return self.conflicts_found / self.conflicts_total if self.conflicts_total else 1.0

    @property
    def errors(self) -> int:
        return (
            self.false_primary + self.intent_wrongly_approvable + self.unsourced + self.duplicates
        )

    def report(self) -> str:
        pct = lambda a, b: f"{a}/{b}" + (f" ({a / b:.0%})" if b else "")  # noqa: E731
        lines = [
            f"Score for '{self.slug}' ({self.candidates} candidates)",
            f"  fact recall          {pct(self.facts_found, self.facts_total)}",
            f"  artist-intent recall {pct(self.intent_found, self.intent_total)}",
            f"  conflict recall      {pct(self.conflicts_found, self.conflicts_total)}",
            f"  false primary        {self.false_primary}   (must be 0)",
            f"  intent approvable    {self.intent_wrongly_approvable}   (must be 0)",
            f"  unsourced            {self.unsourced}   (must be 0)",
            f"  duplicates           {self.duplicates}   (must be 0)",
        ]
        if self.missed:
            lines.append("  missed: " + ", ".join(self.missed))
        return "\n".join(lines)


def score(gold: Gold, proposal: Proposal) -> Score:
    s = Score(slug=gold.slug, candidates=len(proposal.candidates))
    bad_domains = {d.removeprefix("www.") for d in gold.non_primary_domains}

    for item in gold.items:
        hits = [c for c in proposal.candidates if matches(item, c)]
        if item.kind == "fact":
            s.facts_total += 1
            ok = bool(hits)
            s.facts_found += ok
        elif item.kind == "intent":
            s.intent_total += 1
            ok = bool(hits)
            s.intent_found += ok
        elif item.kind == "conflict":
            s.conflicts_total += 1
            ok = any(
                {Stance.supports, Stance.contradicts} <= {src.stance for src in c.sources}
                for c in hits
            )
            s.conflicts_found += ok
        else:
            raise ValueError(f"gold item {item.id}: unknown kind {item.kind!r}")
        if not ok:
            s.missed.append(item.id)

    for i, c in enumerate(proposal.candidates):
        if not c.sources or any(not src.excerpt for src in c.sources):
            s.unsourced += 1
        for src in c.sources:
            dom = _domain(src.url)
            if src.tier == Tier.primary and any(
                dom == d or dom.endswith("." + d) for d in bad_domains
            ):
                s.false_primary += 1
        if c.type == ClaimType.artist_intent and approvable(c):
            s.intent_wrongly_approvable += 1
        s.duplicates += any(_similar(c.body, d.body) >= 0.8 for d in proposal.candidates[:i])
    return s


# ---- reference runs ------------------------------------------------------------------------


def proposal_from_seed(bundle: AlbumBundle) -> Proposal:
    """The reviewed seed as a proposal: the best possible run, used to check the gold set itself."""
    sources = {s.id: s for s in bundle.sources}

    def convert(cs, subject: str, track_number: int | None) -> Candidate:
        return Candidate(
            id=cs.id,
            subject=subject,  # type: ignore[arg-type]
            track_number=track_number,
            type=cs.type,
            depth=cs.depth,
            phase=bundle.phases.get(cs.id),
            body=cs.body,
            body_long=cs.body_long,
            author=cs.author,
            sources=[
                CandidateSource(
                    url=sources[r.ref].url,
                    title=sources[r.ref].title,
                    kind=sources[r.ref].kind,
                    tier=sources[r.ref].tier,
                    stance=r.stance,
                    # Seed excerpts are optional; stand in the body so the structural check passes.
                    excerpt=r.excerpt or cs.body[:200],
                    locator=r.locator,
                )
                for r in cs.sources
            ],
        )

    candidates = [convert(c, "album", None) for c in bundle.album.claims]
    for t in bundle.tracks:
        candidates += [convert(c, "track", t.number) for c in t.claims]
    return Proposal(slug=bundle.album.slug, candidates=candidates)
