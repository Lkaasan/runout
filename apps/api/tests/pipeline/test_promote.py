import yaml
from sqlalchemy import select as sa_select

from app.models import Claim
from app.models.enums import ClaimType, SourceKind, Stance, Status, Tier
from app.pipeline.bootstrap import AlbumInfo, TrackInfo, write_skeleton
from app.pipeline.models import Candidate, CandidateSource, Proposal
from app.pipeline.promote import promote, select
from app.services.importer import import_album
from app.services.seed_loader import load_album


def cand(
    id_,
    body,
    type_=ClaimType.fact,
    *,
    author=None,
    track=None,
    notes=(),
    stances=("supports",),
    url="https://nme.example/r",
):
    return Candidate(
        id=id_,
        type=type_,
        body=body,
        author=author,
        subject="track" if track else "album",
        track_number=track,
        phase="after" if not track else "during",
        notes=list(notes),
        sources=[
            CandidateSource(
                url=url,
                title="NME review",
                kind=SourceKind.press,
                tier=Tier.secondary,
                stance=Stance(st),
                excerpt="a verified quote here",
            )
            for st in stances
        ],
    )


def test_only_clean_claims_are_chosen():
    claims = [
        cand("a", "The album runs 35 minutes."),
        cand(
            "b",
            "The band said they wanted to sound young.",
            ClaimType.artist_intent,
            author="Jim",
        ),
        cand("c", "Critics like it a lot.", ClaimType.interpretation),  # no author
        cand("d", "NME found it warm and loose.", ClaimType.interpretation, author="A Critic"),
        cand("e", "Released on 21 August.", stances=("supports", "contradicts")),
        cand("f", "Recorded in Leeds.", notes=("Overstated: says more than the page",)),
        cand("g", "The album runs 35 minutes in total."),  # repeats a
    ]
    out = select(claims, existing_bodies=[])
    assert [c.id for c in out.chosen] == ["a", "d"]
    reasons = " | ".join(out.skipped)
    assert "artist intent" in reasons and "no named author" in reasons
    assert "contradicts" in reasons and "doubt" in reasons and "repeats" in reasons


def test_what_the_album_already_says_is_not_added_again():
    out = select([cand("a", "The album runs 35 minutes.")], ["The album runs 35 minutes"])
    assert out.chosen == []


def skeleton(tmp_path):
    info = AlbumInfo(
        title="It Goes On",
        artist="Westside Cowboy",
        tracks=[TrackInfo(1, "Kick Stones", 236_000), TrackInfo(2, "Dobro", 165_000)],
    )
    write_skeleton(tmp_path, "it-goes-on", info, [], note="test")


def run_folder(tmp_path, candidates):
    run = tmp_path / "it-goes-on" / "proposals" / "r1"
    run.mkdir(parents=True)
    (run / "proposal.json").write_text(
        Proposal(slug="it-goes-on", candidates=candidates).model_dump_json(), encoding="utf-8"
    )
    return run


def test_promoted_claims_land_in_the_seed_files_and_the_importer_approves_them(tmp_path, session):
    skeleton(tmp_path)
    run = run_folder(
        tmp_path,
        [
            cand("x1", "The album runs 35 minutes.", track=None),
            cand("x2", "Dobro was written on a four-track cassette recorder.", track=2),
            cand("x3", "NME found it warm and loose.", ClaimType.interpretation, author="A Critic"),
            cand(
                "x4",
                "The band wanted to sound young.",
                ClaimType.artist_intent,
                author="Jim",
            ),
        ],
    )
    out = promote(tmp_path, "it-goes-on", run, today="2026-11-23")
    assert len(out.chosen) == 3

    bundle = load_album(tmp_path, "it-goes-on")
    assert {c.id for c in bundle.album.claims} == {"auto-001", "auto-003"}
    assert [c.id for c in bundle.tracks[1].claims] == ["auto-002"]
    assert bundle.tracks[0].claims == []
    assert all(c.reviewed for c in bundle.album.claims)
    assert len(bundle.sources) == 1  # one source, shared by all three claims

    # Comments survive, and the importer approves what satisfies the rules.
    assert "promoted automatically" in (tmp_path / "it-goes-on" / "album.yaml").read_text()
    import_album(session, bundle)
    session.commit()
    status = {c.type: c.status for c in session.scalars(sa_select(Claim))}
    assert status[ClaimType.fact] == Status.approved
    assert status[ClaimType.interpretation] == Status.approved
    assert ClaimType.artist_intent not in status  # never promoted


def test_a_second_promotion_never_reuses_ids_or_sources(tmp_path):
    skeleton(tmp_path)
    run = run_folder(tmp_path, [cand("p", "First fact about the record.")])
    promote(tmp_path, "it-goes-on", run, today="d1")
    run2 = run_folder(tmp_path / "again", [])  # separate folder for the second proposal file
    (run2 / "proposal.json").write_text(
        Proposal(
            slug="it-goes-on", candidates=[cand("p", "A completely different second fact.")]
        ).model_dump_json(),
        encoding="utf-8",
    )
    promote(tmp_path, "it-goes-on", run2, today="d2")
    ids = [c.id for c in load_album(tmp_path, "it-goes-on").album.claims]
    assert ids == ["auto-001", "auto-002"]
    sources = yaml.safe_load((tmp_path / "it-goes-on" / "sources.yaml").read_text())["sources"]
    assert len(sources) == 1  # same address, same source
