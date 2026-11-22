"""Writes a run to disk: seed-style YAML for review, JSON for scoring, and a report.

Proposals live in `content/albums/<slug>/proposals/<run-id>/` and are never read by the importer.
A person reviews them (in a pull request) and copies the claims they accept into the seed files.
Every claim is written with `reviewed: false`: the finder cannot approve anything.
"""

import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import yaml

from app.models.enums import Tier
from app.pipeline.models import Proposal
from app.pipeline.run import RunResult
from app.pipeline.scoring import approvable
from app.services.seed_schema import ClaimSeed, SourceSeed

HEADER = (
    "# PROPOSED by the information finder. Nothing here is reviewed or approved.\n"
    "# Check each claim against its excerpt, then copy what you accept into the album's seed\n"
    "# files (claims and sources). Delete this folder when done.\n"
)


def _source_ids(proposal: Proposal) -> dict[str, str]:
    """One stable, unique id per distinct source URL."""
    ids: dict[str, str] = {}
    used: set[str] = set()
    for c in proposal.candidates:
        for s in c.sources:
            key = s.url or s.title
            if key in ids:
                continue
            base = re.sub(r"[^a-z0-9]+", "-", s.title.lower()).strip("-")[:40] or "source"
            sid, n = base, 2
            while sid in used:
                sid, n = f"{base}-{n}", n + 1
            ids[key] = sid
            used.add(sid)
    return ids


def to_seed_documents(proposal: Proposal) -> tuple[list[dict], list[dict]]:
    """(sources, claims) in the seed vocabulary, ready to validate with the seed schema."""
    ids = _source_ids(proposal)
    sources: dict[str, dict] = {}
    claims: list[dict] = []
    for c in proposal.candidates:
        refs = []
        for s in c.sources:
            sid = ids[s.url or s.title]
            sources.setdefault(
                sid,
                {
                    "id": sid,
                    "kind": s.kind.value,
                    "title": s.title,
                    "url": s.url,
                    "tier": s.tier.value,
                },
            )
            refs.append(
                {
                    "ref": sid,
                    "stance": s.stance.value,
                    "excerpt": s.excerpt,
                    **({"locator": s.locator} if s.locator else {}),
                }
            )
        claims.append(
            {
                "track": c.track_number if c.subject == "track" else "album",
                "id": c.id,
                "type": c.type.value,
                "depth": c.depth.value,
                "phase": (
                    c.phase.value if c.phase else ("during" if c.subject == "track" else "before")
                ),
                "body": c.body,
                **({"body_long": c.body_long} if c.body_long else {}),
                **({"author": c.author} if c.author else {}),
                "reviewed": False,
                "sources": refs,
            }
        )
    return list(sources.values()), claims


def validate_documents(sources: list[dict], claims: list[dict]) -> list[str]:
    """Check rendered documents with the same models the importer uses. Returns problems."""
    problems: list[str] = []
    for s in sources:
        try:
            SourceSeed.model_validate(s)
        except ValueError as exc:
            problems.append(f"source {s.get('id')}: {exc}")
    known = {s["id"] for s in sources}
    for c in claims:
        body = {k: v for k, v in c.items() if k != "track"}
        try:
            seed = ClaimSeed.model_validate(body)
        except ValueError as exc:
            problems.append(f"claim {c.get('id')}: {exc}")
            continue
        if seed.reviewed:
            problems.append(f"claim {seed.id}: the finder must not set reviewed")
        problems += [
            f"claim {seed.id}: unknown source {r.ref}" for r in seed.sources if r.ref not in known
        ]
    return problems


def render_report(result: RunResult, run_id: str) -> str:
    cands = result.proposal.candidates
    by_type = Counter(c.type.value for c in cands)
    would_approve = [c for c in cands if approvable(c)]
    lines = [
        f"# Information finder run {run_id} for `{result.proposal.slug}`",
        "",
        result.summary(),
        "",
        "## What the rules would do",
        "",
        f"- {len(cands)} proposals: " + ", ".join(f"{n} {t}" for t, n in sorted(by_type.items())),
        f"- {len(would_approve)} could be approved automatically if marked reviewed "
        "(they have supporting sources and the right tier). Everything else needs better sources.",
        f"- {sum(1 for c in cands if c.type.value == 'artist_intent')} artist-intent claims: "
        "none can be approved until a primary source (the original interview or book) is found.",
        "",
        "## Dropped",
        "",
    ]
    lines += [f"- **{d.reason}**: {d.body[:120]}" for d in result.dropped] or ["- nothing"]
    lines += ["", "## Proposals", ""]
    for c in cands:
        where = f"track {c.track_number}" if c.subject == "track" else "album"
        lines.append(f"### {c.id} ({c.type.value}, {where}, {c.depth.value})")
        lines.append(c.body)
        for s in c.sources:
            tier = "" if s.tier != Tier.primary else " PRIMARY"
            lines.append(f'- {s.stance.value} [{s.title}]({s.url}){tier}: "{s.excerpt}"')
        lines.append("")
    return "\n".join(lines)


def write_run(result: RunResult, content_dir: Path, *, run_id: str | None = None) -> Path:
    run_id = run_id or datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    folder = content_dir / result.proposal.slug / "proposals" / run_id
    folder.mkdir(parents=True, exist_ok=True)

    sources, claims = to_seed_documents(result.proposal)
    problems = validate_documents(sources, claims)
    if problems:
        raise ValueError("The finder produced an invalid proposal:\n" + "\n".join(problems))

    document = yaml.safe_dump(
        {"sources": sources, "claims": claims}, sort_keys=False, allow_unicode=True, width=100
    )
    (folder / "proposal.yaml").write_text(HEADER + document, encoding="utf-8")
    (folder / "proposal.json").write_text(
        result.proposal.model_dump_json(indent=1), encoding="utf-8"
    )
    (folder / "report.md").write_text(render_report(result, run_id), encoding="utf-8")
    return folder
