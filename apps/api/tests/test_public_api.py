from sqlalchemy.orm import Session

from app.models import Claim, Link, Track
from app.models.enums import Status


def test_empty_shelf(client):
    assert client.get("/albums").json() == []


def test_shelf_lists_album(seeded):
    (album,) = seeded.get("/albums").json()
    assert album["slug"] == "placeholder-album"
    assert album["artist"] == "Placeholder Artist"


def test_unknown_album_and_track_are_404(seeded):
    assert seeded.get("/albums/nope").status_code == 404
    assert seeded.get("/albums/placeholder-album/tracks/99").status_code == 404


def test_album_detail_has_only_approved_claims(seeded):
    album = seeded.get("/albums/placeholder-album").json()
    assert [t["title"] for t in album["tracks"]] == ["Opener", "Closer"]
    # contested-date is a flagged draft, so it is absent
    assert [c["body"][:8] for c in album["before"]] == ["Recorded"]
    assert [c["type"] for c in album["after"]] == ["interpretation"]
    assert album["after"][0]["author"] == "Placeholder Critic"
    assert album["credits"] == [{"person": "Pat Producer", "role": "producer"}]


def test_depth_filter(seeded):
    listen = seeded.get("/albums/placeholder-album", params={"depth": "listen"}).json()
    assert len(listen["before"]) == 1
    assert listen["after"] == []  # the only approved 'after' claim is study depth
    study = seeded.get("/albums/placeholder-album", params={"depth": "study"}).json()
    assert study["before"] == []
    assert len(study["after"]) == 1
    assert seeded.get("/albums/placeholder-album", params={"depth": "bogus"}).status_code == 422


def test_track_detail(seeded):
    track = seeded.get("/albums/placeholder-album/tracks/1").json()
    assert track["between"] is None  # opener-intro is an unreviewed draft
    (moment,) = track["moments"]
    assert (moment["start_ms"], moment["end_ms"]) == (45_000, 60_000)
    assert moment["claim"]["sources"][0]["source"]["title"].startswith("Placeholder Artist")
    (annotation,) = track["annotations"]
    assert (annotation["line_start"], annotation["line_end"]) == (2, 4)
    (link,) = track["links"]
    assert link["relation"] == "samples" and link["target_title"] == "Original Break"
    assert track["credits"] == [{"person": "Sam Drummer", "role": "drums"}]


def test_draft_claims_never_appear_publicly(seeded, engine):
    with Session(engine) as s:
        for c in s.query(Claim):
            c.status = Status.draft
        s.commit()
    album = seeded.get("/albums/placeholder-album").json()
    assert album["before"] == [] and album["after"] == []
    track = seeded.get("/albums/placeholder-album/tracks/1").json()
    assert track["moments"] == [] and track["annotations"] == [] and track["links"] == []
    assert track["between"] is None


def test_rejected_claims_never_appear_publicly(seeded, engine):
    with Session(engine) as s:
        claim = s.query(Claim).filter_by(key="placeholder-album/drum-sample").one()
        claim.status = Status.rejected
        s.commit()
    track = seeded.get("/albums/placeholder-album/tracks/1").json()
    assert track["moments"] == [] and track["links"] == []


def test_entity_card_links_both_directions(seeded, engine):
    with Session(engine) as s:
        t1 = s.query(Track).filter_by(number=1).one().id
        t2 = s.query(Track).filter_by(number=2).one().id
        s.query(Link).one().to_id = t2
        s.commit()
    out = seeded.get(f"/entities/track/{t1}").json()
    assert out["name"] == "Opener"
    assert [link["relation"] for link in out["links_out"]] == ["samples"]
    incoming = seeded.get(f"/entities/track/{t2}").json()
    assert [link["from_id"] for link in incoming["links_in"]] == [t1]
    assert seeded.get("/entities/track/9999").status_code == 404
    assert seeded.get("/entities/nonsense/1").status_code == 422
