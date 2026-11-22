"""One extraction run: pages in, checked proposals out."""

from collections import Counter
from dataclasses import dataclass, field

from app.pipeline.checks import Dropped, check_all, drop_existing, merge_duplicates
from app.pipeline.extractor import extract_pages
from app.pipeline.llm import LLMBackend
from app.pipeline.models import Page, Proposal
from app.services.seed_loader import AlbumBundle


@dataclass
class RunResult:
    proposal: Proposal
    dropped: list[Dropped] = field(default_factory=list)
    merged: int = 0
    proposed_by_model: int = 0
    notes: list[str] = field(default_factory=list)

    def summary(self) -> str:
        reasons = Counter(d.reason for d in self.dropped)
        lines = [
            f"{len(self.proposal.candidates)} candidate(s) kept "
            f"({self.proposed_by_model} proposed by the model, {self.merged} merged as duplicates, "
            f"{len(self.dropped)} dropped).",
        ]
        lines += [f"  dropped: {n} x {reason}" for reason, n in reasons.most_common()]
        lines += [f"  note: {n}" for n in self.notes]
        return "\n".join(lines)


def existing_bodies(bundle: AlbumBundle) -> list[str]:
    return [c.body for c in bundle.album.claims] + [c.body for t in bundle.tracks for c in t.claims]


def run_extraction(
    bundle: AlbumBundle,
    pages: list[Page],
    backend: LLMBackend,
    *,
    skip_existing: bool = True,
) -> RunResult:
    """Ask the model for claims, then keep only what the deterministic checks accept.

    `skip_existing` drops proposals the seed already says. Turn it off to measure the finder
    against a gold set built from that same seed.
    """
    tracks = [(t.number, t.title) for t in bundle.tracks]
    extraction = extract_pages(backend, bundle.album.title, bundle.album.artist.name, tracks, pages)
    checked = check_all(extraction.raw_claims, pages)
    candidates, merged = merge_duplicates(checked.candidates)
    dropped = list(checked.dropped)
    if skip_existing:
        candidates, already = drop_existing(candidates, existing_bodies(bundle))
        dropped += already

    # Stable, readable ids after merging.
    for n, c in enumerate(candidates, start=1):
        c.id = f"proposed-{n:03d}"

    return RunResult(
        proposal=Proposal(slug=bundle.album.slug, candidates=candidates),
        dropped=dropped,
        merged=merged,
        proposed_by_model=len(extraction.raw_claims),
        notes=extraction.notes,
    )
