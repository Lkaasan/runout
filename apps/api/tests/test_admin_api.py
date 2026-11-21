import base64

import pytest

from app.config import settings
from tests.conftest import CONTENT

SLUG = "placeholder-album"


@pytest.fixture(autouse=True)
def admin_password(monkeypatch):
    monkeypatch.setattr(settings, "admin_password", "secret")


def auth(password="secret"):
    token = base64.b64encode(f"admin:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def drafts(client):
    queue = client.get("/admin/claims", headers=auth()).json()
    return {c["key"].split("/")[1]: c for c in queue}


def patch(client, claim, **body):
    return client.patch(f"/admin/claims/{claim['id']}", json=body, headers=auth())


def test_requires_password(seeded):
    assert seeded.get("/admin/claims").status_code == 401
    assert seeded.get("/admin/claims", headers=auth("wrong")).status_code == 401
    assert seeded.get("/admin/claims", headers=auth()).status_code == 200


def test_disabled_without_configured_password(seeded, monkeypatch):
    monkeypatch.setattr(settings, "admin_password", "")
    assert seeded.get("/admin/claims", headers=auth("")).status_code == 503


def test_queue_lists_drafts_flagged_first_with_problems(seeded):
    queue = seeded.get("/admin/claims", headers=auth()).json()
    assert queue[0]["key"] == f"{SLUG}/contested-date"
    assert queue[0]["flagged"] is True
    by_key = drafts(seeded)
    assert set(by_key) == {"contested-date", "opener-intro", "closer-intro", "unsourced-fact"}
    assert by_key["unsourced-fact"]["problems"] == ["A fact needs at least one supporting source."]
    assert by_key["opener-intro"]["problems"] == []


def test_approving_sourceless_fact_is_blocked_with_reasons(seeded):
    r = patch(seeded, drafts(seeded)["unsourced-fact"], status="approved")
    assert r.status_code == 422
    assert "supporting source" in r.json()["detail"]["violations"][0]
    assert "unsourced-fact" in drafts(seeded)  # still a draft


def test_failed_approval_does_not_save_edits(seeded):
    r = patch(seeded, drafts(seeded)["unsourced-fact"], status="approved", body="changed")
    assert r.status_code == 422
    assert drafts(seeded)["unsourced-fact"]["body"] != "changed"


def test_approve_makes_claim_public(seeded):
    claim = drafts(seeded)["opener-intro"]
    r = patch(seeded, claim, status="approved")
    assert r.status_code == 200 and r.json()["status"] == "approved"
    assert seeded.get(f"/albums/{SLUG}/tracks/1").json()["between"]["id"] == claim["id"]


def test_human_can_approve_flagged_claim_and_reject_others(seeded):
    assert patch(seeded, drafts(seeded)["contested-date"], status="approved").status_code == 200
    other = drafts(seeded)["closer-intro"]
    assert patch(seeded, other, status="rejected").json()["status"] == "rejected"
    rejected = seeded.get("/admin/claims?status=rejected", headers=auth()).json()
    assert rejected[0]["id"] == other["id"]


def test_edit_text(seeded):
    r = patch(seeded, drafts(seeded)["opener-intro"], body="New text")
    assert r.json()["body"] == "New text" and r.json()["status"] == "draft"


def test_patch_unknown_claim(seeded):
    assert seeded.patch("/admin/claims/9999", json={}, headers=auth()).status_code == 404


def test_import_endpoint(client, monkeypatch):
    monkeypatch.setattr(settings, "content_dir", CONTENT)
    r = client.post(f"/admin/import/{SLUG}", headers=auth())
    assert r.status_code == 200
    assert r.json()["claims"] == 8
    assert len(client.get("/albums").json()) == 1
    bad = client.post("/admin/import/nope", headers=auth())
    assert bad.status_code == 422 and "not found" in bad.json()["detail"]["violations"][0]
