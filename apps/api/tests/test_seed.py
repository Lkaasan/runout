import shutil
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.models import Album, Annotation, Claim, Credit, Link, Moment, Source, Track
from app.models.enums import Status
from app.services.importer import import_album
from app.services.seed_loader import SeedValidationError, load_album
from app.services.seed_schema import parse_time_ms

CONTENT = Path(__file__).resolve().parents[3] / "content" / "albums"
SLUG = "placeholder-album"


def count(session, model):
    return session.scalar(select(func.count()).select_from(model))


def test_parse_time_ms():
    assert parse_time_ms("2:14") == 134_000
    assert parse_time_ms("1:02:03") == 3_723_000
    assert parse_time_ms("0:05.5") == 5_500
    with pytest.raises(ValueError, match="quoted"):
        parse_time_ms(134)
    with pytest.raises(ValueError, match="invalid"):
        parse_time_ms("2:99")


def test_imports_placeholder_album(session):
    report = import_album(session, load_album(CONTENT, SLUG))
    session.commit()

    assert (report.tracks, report.sources, report.claims) == (2, 2, 8)
    assert count(session, Album) == 1
    assert count(session, Track) == 2
    assert count(session, Moment) == 1
    assert count(session, Annotation) == 1
    assert count(session, Link) == 1
    assert count(session, Credit) == 2

    claims = {c.key: c for c in session.scalars(select(Claim))}
    approved = {k.split("/")[1] for k, c in claims.items() if c.status == Status.approved}
    assert approved == {"how-it-was-made", "legacy", "drum-sample", "verse-meaning"}
    # A contradicted claim is flagged and not auto-approved; the importer says why.
    assert claims[f"{SLUG}/contested-date"].flagged
    assert claims[f"{SLUG}/contested-date"].status == Status.draft
    assert any("contested-date" in w for w in report.warnings)
    # Phases are derived from how a claim is used.
    assert claims[f"{SLUG}/drum-sample"].phase == "during"
    assert claims[f"{SLUG}/closer-intro"].phase == "between"

    moment = session.scalar(select(Moment))
    assert (moment.start_ms, moment.end_ms) == (45_000, 60_000)
    assert session.scalar(select(Track).filter_by(number=1)).duration_ms == 190_000


def test_reimport_is_idempotent_and_keeps_review_decisions(session):
    bundle = load_album(CONTENT, SLUG)
    import_album(session, bundle)
    # An admin approves a draft by hand.
    intro = session.scalar(select(Claim).filter_by(key=f"{SLUG}/opener-intro"))
    intro.status = Status.approved
    session.commit()

    models = (Album, Track, Claim, Source, Moment, Link, Credit)
    before = {m: count(session, m) for m in models}
    import_album(session, bundle)
    session.commit()

    assert before == {m: count(session, m) for m in models}
    session.refresh(intro)
    assert intro.status == Status.approved


@pytest.fixture
def content(tmp_path):
    shutil.copytree(CONTENT / SLUG, tmp_path / SLUG)
    return tmp_path


def edit(content: Path, rel: str, *replacements: tuple[str, str]) -> None:
    path = content / SLUG / rel
    text = path.read_text(encoding="utf-8")
    for old, new in replacements:
        assert old in text, old
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")


def errors_for(content: Path) -> list[str]:
    with pytest.raises(SeedValidationError) as exc:
        load_album(content, SLUG)
    return [str(e) for e in exc.value.errors]


def test_changed_text_resets_approved_claim_to_draft(session, content):
    import_album(session, load_album(content, SLUG))
    intro = session.scalar(select(Claim).filter_by(key=f"{SLUG}/opener-intro"))
    intro.status = Status.approved
    session.commit()

    edit(content, "tracks/01-opener.yaml", ("The first song", "The very first song"))
    import_album(session, load_album(content, SLUG))
    session.refresh(intro)
    assert intro.status == Status.draft


def test_missing_album_directory(tmp_path):
    with pytest.raises(SeedValidationError, match="not found"):
        load_album(tmp_path, "nope")


def test_invalid_yaml_reports_file_and_line(content):
    (content / SLUG / "sources.yaml").write_text("sources: [unclosed\n")
    errs = errors_for(content)
    assert any("sources.yaml" in e and "invalid YAML" in e and "line" in e for e in errs)


def test_schema_errors_report_file_path_and_reason(content):
    edit(content, "tracks/01-opener.yaml", ('at: "0:45"', "at: 45"), ("number: 1", "number: 0"))
    errs = errors_for(content)
    assert any("01-opener.yaml: moments[0].at:" in e and "quoted" in e for e in errs)
    assert any("01-opener.yaml: number:" in e for e in errs)


def test_unknown_references_and_missing_phase(content):
    edit(
        content,
        "tracks/01-opener.yaml",
        ("ref: interview-1", "ref: nope"),
        ("claim: verse-meaning", "claim: ghost"),
    )
    errs = errors_for(content)
    assert any("unknown source 'nope'" in e for e in errs)
    assert any("annotations[0].claim: unknown claim 'ghost'" in e for e in errs)
    # verse-meaning is now unused and has no explicit phase.
    assert any("phase is required" in e for e in errs)


def test_unknown_field_is_rejected(content):
    path = content / SLUG / "album.yaml"
    path.write_text(path.read_text(encoding="utf-8") + "typo_field: 1\n", encoding="utf-8")
    assert any("typo_field" in e for e in errors_for(content))


def test_every_album_in_content_is_valid_and_imports(session):
    """Real albums must stay valid as the rules and schema evolve."""
    slugs = sorted(p.name for p in CONTENT.iterdir() if p.is_dir())
    assert "animals" in slugs
    for slug in slugs:
        report = import_album(session, load_album(CONTENT, slug))
        assert report.claims > 0


def test_animals_artist_intent_stays_draft_without_primary_sources(session):
    import_album(session, load_album(CONTENT, "animals"))
    session.commit()
    intent = session.scalars(select(Claim).filter_by(type="artist_intent")).all()
    animals = [c for c in intent if c.key.startswith("animals/")]
    assert animals and all(c.status == Status.draft for c in animals)
    contested = session.scalar(select(Claim).filter_by(key="animals/pig-size"))
    assert contested.flagged and contested.status == Status.draft
