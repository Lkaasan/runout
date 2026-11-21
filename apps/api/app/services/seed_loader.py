"""Reads and validates an album's seed files. Reports file, path and reason for every error."""

from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError

from app.models.enums import Phase
from app.services.seed_schema import AlbumSeed, SourceSeed, SourcesFile, TrackSeed


@dataclass(frozen=True)
class SeedError:
    file: str
    path: str
    reason: str

    def __str__(self) -> str:
        where = f"{self.file}: {self.path}" if self.path else self.file
        return f"{where}: {self.reason}"


class SeedValidationError(Exception):
    def __init__(self, errors: list[SeedError]):
        self.errors = errors
        super().__init__("\n".join(str(e) for e in errors))


@dataclass
class AlbumBundle:
    album: AlbumSeed
    sources: list[SourceSeed]
    tracks: list[TrackSeed]
    # claim id -> resolved phase
    phases: dict[str, Phase] = field(default_factory=dict)


def _format_path(loc: tuple) -> str:
    out = ""
    for part in loc:
        out += f"[{part}]" if isinstance(part, int) else (f".{part}" if out else str(part))
    return out


def _read_yaml(path: Path, rel: str, errors: list[SeedError]):
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        line = f"line {mark.line + 1}: " if mark else ""
        errors.append(SeedError(rel, "", f"invalid YAML, {line}{getattr(exc, 'problem', exc)}"))
    except OSError as exc:
        errors.append(SeedError(rel, "", f"cannot read file: {exc.strerror}"))
    return None


def _parse[M: BaseModel](model: type[M], data, rel: str, errors: list[SeedError]) -> M | None:
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        for err in exc.errors():
            errors.append(SeedError(rel, _format_path(err["loc"]), err["msg"]))
    return None


def load_album(content_dir: Path, slug: str) -> AlbumBundle:
    root = content_dir / slug
    if not root.is_dir():
        raise SeedValidationError([SeedError(str(root), "", "album directory not found")])

    errors: list[SeedError] = []

    album_data = _read_yaml(root / "album.yaml", f"{slug}/album.yaml", errors)
    album = _parse(AlbumSeed, album_data, f"{slug}/album.yaml", errors)
    if album and album.slug != slug:
        errors.append(
            SeedError(f"{slug}/album.yaml", "slug", f"must match directory name '{slug}'")
        )

    sources: list[SourceSeed] = []
    sources_data = _read_yaml(root / "sources.yaml", f"{slug}/sources.yaml", errors)
    parsed_sources = _parse(SourcesFile, sources_data, f"{slug}/sources.yaml", errors)
    if parsed_sources:
        sources = parsed_sources.sources

    tracks: list[tuple[str, TrackSeed]] = []
    for path in sorted((root / "tracks").glob("*.yaml")):
        rel = f"{slug}/tracks/{path.name}"
        track = _parse(TrackSeed, _read_yaml(path, rel, errors), rel, errors)
        if track:
            tracks.append((rel, track))

    if errors or album is None:
        raise SeedValidationError(errors)

    bundle = AlbumBundle(album=album, sources=sources, tracks=[t for _, t in tracks])
    _check_references(bundle, slug, tracks, errors)
    if errors:
        raise SeedValidationError(errors)
    return bundle


def _check_references(
    bundle: AlbumBundle, slug: str, tracks: list[tuple[str, TrackSeed]], errors: list[SeedError]
) -> None:
    album_file = f"{slug}/album.yaml"
    sources_file = f"{slug}/sources.yaml"

    source_ids: set[str] = set()
    for i, s in enumerate(bundle.sources):
        if s.id in source_ids:
            errors.append(SeedError(sources_file, f"sources[{i}].id", f"duplicate id '{s.id}'"))
        source_ids.add(s.id)

    claim_ids: dict[str, str] = {}
    seen_tracks: dict[tuple[int, int], str] = {}
    all_claims: list = []
    groups = [(album_file, bundle.album.claims)] + [(rel, t.claims) for rel, t in tracks]
    for rel, claims in groups:
        for i, claim in enumerate(claims):
            if claim.id in claim_ids:
                errors.append(
                    SeedError(
                        rel,
                        f"claims[{i}].id",
                        f"duplicate claim id '{claim.id}' (also in {claim_ids[claim.id]})",
                    )
                )
            claim_ids[claim.id] = rel
            all_claims.append((rel, f"claims[{i}]", claim))
            for j, cs in enumerate(claim.sources):
                if cs.ref not in source_ids:
                    errors.append(
                        SeedError(
                            rel, f"claims[{i}].sources[{j}].ref", f"unknown source '{cs.ref}'"
                        )
                    )

    used_as: dict[str, set[Phase]] = {}

    def use(rel: str, path: str, claim_id: str, phase: Phase | None) -> None:
        if claim_id not in claim_ids:
            errors.append(SeedError(rel, path, f"unknown claim '{claim_id}'"))
        elif phase:
            used_as.setdefault(claim_id, set()).add(phase)

    for rel, t in tracks:
        key = (t.disc, t.number)
        if key in seen_tracks:
            errors.append(
                SeedError(rel, "number", f"duplicate track {t.number} (also {seen_tracks[key]})")
            )
        seen_tracks[key] = rel
        if t.between:
            use(rel, "between.claim", t.between.claim, Phase.between)
        for i, m in enumerate(t.moments):
            use(rel, f"moments[{i}].claim", m.claim, Phase.during)
        for i, a in enumerate(t.annotations):
            use(rel, f"annotations[{i}].claim", a.claim, Phase.during)
        for i, link in enumerate(t.links):
            if link.claim:
                use(rel, f"links[{i}].claim", link.claim, None)
    for i, link in enumerate(bundle.album.links):
        if link.claim:
            use(album_file, f"links[{i}].claim", link.claim, None)

    for rel, path, claim in all_claims:
        needed = used_as.get(claim.id, set())
        if len(needed) > 1:
            errors.append(
                SeedError(rel, path, "used in conflicting phases: " + ", ".join(sorted(needed)))
            )
        elif needed:
            (phase,) = needed
            if claim.phase and claim.phase != phase:
                errors.append(
                    SeedError(
                        rel,
                        f"{path}.phase",
                        f"claim is used as '{phase}' but declares '{claim.phase}'",
                    )
                )
            bundle.phases[claim.id] = phase
        elif claim.phase:
            bundle.phases[claim.id] = claim.phase
        else:
            errors.append(
                SeedError(
                    rel,
                    f"{path}.phase",
                    "phase is required for a claim not used by a moment, annotation or 'between'",
                )
            )
