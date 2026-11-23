"""Moving the clean part of a finder run into the album's real seed files.

A run's proposals are drafts in a folder the importer ignores. `promote` is the step that makes
some of them part of the album: it copies chosen claims (and the sources they cite) into
`album.yaml`, `sources.yaml` and the track files, marked `reviewed: true`, so the importer approves
those that satisfy the claim rules.

That is a decision, not a formality, so the defaults are cautious and the result is plain text in
git, shown in a pull request:

- facts and trivia with no doubt attached (not contradicted, not overstated, type fits);
- interpretations only when a person is named, shown as theirs;
- NEVER artist intent: those need a primary source a person has confirmed (see `trace`);
- near-duplicates of something already chosen or already in the album are skipped.
"""

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from app.models.enums import ClaimType, Stance
from app.pipeline.checks import DUPLICATE_THRESHOLD
from app.pipeline.models import Candidate, Proposal
from app.pipeline.render import to_seed_documents, validate_documents
from app.pipeline.scoring import similarity
from app.services.seed_loader import AlbumBundle, load_album

_DOUBT = ("Overstated", "Type may be wrong", "Not verified", "Disputed")


def doubt(c: Candidate) -> str | None:
    """Why a reviewer should look before this goes live, or None if nothing flags it."""
    if any(s.stance == Stance.contradicts for s in c.sources):
        return "a source contradicts it"
    if any(n.startswith(_DOUBT) for n in c.notes):
        return "the verifier or conflict check raised a doubt"
    if not any(s.stance == Stance.supports and s.excerpt for s in c.sources):
        return "no supporting quote"
    return None


@dataclass
class Selection:
    chosen: list[Candidate] = field(default_factory=list)
    skipped: Counter = field(default_factory=Counter)


def select(candidates: list[Candidate], existing_bodies: list[str]) -> Selection:
    out = Selection()
    taken = list(existing_bodies)
    for c in candidates:
        if c.type == ClaimType.artist_intent:
            out.skipped["artist intent (needs a confirmed primary source)"] += 1
        elif c.type == ClaimType.interpretation and not c.author:
            out.skipped["opinion with no named author"] += 1
        elif reason := doubt(c):
            out.skipped[reason] += 1
        elif any(similarity(c.body, t) >= DUPLICATE_THRESHOLD for t in taken):
            out.skipped["repeats something already chosen"] += 1
        else:
            out.chosen.append(c)
            taken.append(c.body)
    return out


# ---- writing -----------------------------------------------------------------------------------


def _read(path: Path) -> tuple[list[str], dict]:
    """(leading comment lines, parsed data). Comments are kept when the file is rewritten."""
    text = path.read_text("utf-8")
    comments = [ln for ln in text.splitlines() if ln.startswith("#")]
    return comments, yaml.safe_load(text) or {}


def _write(path: Path, comments: list[str], data: dict) -> None:
    body = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100)
    path.write_text(("\n".join(comments) + "\n" if comments else "") + body, encoding="utf-8")


def _next_number(bundle: AlbumBundle) -> int:
    ids = [c.id for c in bundle.album.claims] + [c.id for t in bundle.tracks for c in t.claims]
    nums = [int(m.group(1)) for i in ids if (m := re.fullmatch(r"auto-(\d+)", i))]
    return max(nums, default=0) + 1


def promote(content_dir: Path, slug: str, run: Path, *, today: str) -> Selection:
    """Copy the selected claims of a run into the album's seed files. Returns what was done."""
    bundle = load_album(content_dir, slug)
    proposal = Proposal.model_validate_json((run / "proposal.json").read_text("utf-8"))
    existing = [c.body for c in bundle.album.claims] + [
        c.body for t in bundle.tracks for c in t.claims
    ]
    selection = select(proposal.candidates, existing)
    if not selection.chosen:
        return selection

    # Fresh ids that cannot collide with earlier promotions.
    start = _next_number(bundle)
    for offset, c in enumerate(selection.chosen):
        c.id = f"auto-{start + offset:03d}"

    sources, claims = to_seed_documents(Proposal(slug=slug, candidates=selection.chosen))
    problems = validate_documents(sources, claims)  # as proposals: nothing marked reviewed yet
    if problems:
        raise ValueError("Cannot promote:\n" + "\n".join(problems))
    for c in claims:
        c["reviewed"] = True  # the one place a finder claim is marked reviewed: this step

    folder = content_dir / slug
    note = (
        f"# {len(claims)} claims promoted automatically from proposals/{run.name} on {today}. "
        "A first pass,"
        "\n# not read one by one: facts and trivia nothing doubted, and named critics' views."
    )

    # sources.yaml: add new ones, reusing ids already there for the same address.
    src_comments, src_data = _read(folder / "sources.yaml")
    have = {s["url"]: s["id"] for s in src_data.get("sources") or [] if s.get("url")}
    taken_ids = {s["id"] for s in src_data.get("sources") or []}
    rename: dict[str, str] = {}
    for s in sources:
        if s["url"] in have:
            rename[s["id"]] = have[s["url"]]
            continue
        new_id, n = s["id"], 2
        while new_id in taken_ids:
            new_id, n = f"{s['id']}-{n}", n + 1
        rename[s["id"]] = new_id
        taken_ids.add(new_id)
        have[s["url"]] = new_id
        src_data.setdefault("sources", []).append({**s, "id": new_id})
    _write(folder / "sources.yaml", src_comments, src_data)

    for c in claims:
        for ref in c["sources"]:
            ref["ref"] = rename[ref["ref"]]

    # album.yaml and the track files.
    album_claims = [c for c in claims if c["track"] == "album"]
    cm, data = _read(folder / "album.yaml")
    if album_claims:
        data.setdefault("claims", []).extend(
            {k: v for k, v in c.items() if k != "track"} for c in album_claims
        )
        _write(folder / "album.yaml", [*cm, note], data)
    by_track: dict[int, list[dict]] = {}
    for c in claims:
        if c["track"] != "album":
            by_track.setdefault(c["track"], []).append({k: v for k, v in c.items() if k != "track"})
    for path in sorted((folder / "tracks").glob("*.yaml")):
        cm, data = _read(path)
        if data.get("number") in by_track:
            data.setdefault("claims", []).extend(by_track.pop(data["number"]))
            _write(path, [*cm, note], data)
    if by_track:
        raise ValueError(f"No track file for numbers {sorted(by_track)}")

    load_album(content_dir, slug)  # the result must still be a valid album
    return selection
