from datetime import UTC, datetime

import pytest

from app.models.enums import ClaimType, Tier
from app.pipeline.checks import (
    Dropped,
    check_all,
    check_claim,
    drop_existing,
    excerpt_in_page,
    is_lyric_domain,
    merge_duplicates,
    normalize,
)
from app.pipeline.models import Candidate, CandidateSource, Page

TEXT = (
    "Animals is the tenth studio album by the English rock band Pink Floyd, released on "
    "21 January 1977.  The cover was conceived by Roger Waters — a photograph of "
    "Battersea Power Station with an inflatable “pig” between its chimneys."
)


def page(text=TEXT, url="https://en.wikipedia.org/wiki/Animals", kind="wikipedia") -> Page:
    return Page(url=url, title="Animals", kind=kind, fetched_at=datetime.now(UTC), text=text)


def raw(**kw) -> dict:
    base = {
        "subject": "album",
        "type": "fact",
        "depth": "listen",
        "phase": "before",
        "body": "Animals is Pink Floyd's tenth studio album.",
        "evidence": [
            {
                "page": 0,
                "excerpt": "the tenth studio album by the English rock band",
                "stance": "supports",
            }
        ],
    }
    return {**base, **kw}


# ---- excerpt verification -------------------------------------------------------------------


def test_exact_excerpt_is_found():
    assert excerpt_in_page("tenth studio album by the English rock band", TEXT)


def test_spacing_quotes_and_dashes_do_not_matter():
    assert excerpt_in_page("released on 21 January 1977. The cover", TEXT)  # double space in page
    assert excerpt_in_page("Waters - a photograph of Battersea", TEXT)  # em dash vs hyphen
    assert excerpt_in_page('an inflatable "pig" between its chimneys', TEXT)  # curly quotes


def test_changed_words_or_case_are_not_found():
    assert not excerpt_in_page("the ninth studio album by the English rock band", TEXT)
    assert not excerpt_in_page("THE TENTH STUDIO ALBUM", TEXT)
    assert not excerpt_in_page("tenth album by the English rock band", TEXT)  # a word removed
    assert not excerpt_in_page("", TEXT)


def test_normalize_is_idempotent():
    once = normalize(TEXT)
    assert normalize(once) == once


# ---- one claim ------------------------------------------------------------------------------


def test_good_claim_becomes_a_candidate_with_code_assigned_source_fields():
    c = check_claim(raw(), [page()], "proposed-001")
    assert isinstance(c, Candidate)
    (src,) = c.sources
    # The model never chooses these: they come from the page it cited.
    assert src.url == "https://en.wikipedia.org/wiki/Animals"
    assert src.tier == Tier.tertiary
    assert c.id == "proposed-001"


def test_invented_excerpt_is_dropped():
    bad = raw(
        evidence=[
            {
                "page": 0,
                "excerpt": "recorded entirely in a single week in Kent",
                "stance": "supports",
            }
        ]
    )
    out = check_claim(bad, [page()], "x")
    assert isinstance(out, Dropped) and "not in the page" in out.reason


def test_evidence_pointing_at_a_missing_page_is_dropped():
    out = check_claim(
        raw(evidence=[{"page": 5, "excerpt": "a b c d e", "stance": "supports"}]), [page()], "x"
    )
    assert isinstance(out, Dropped) and "does not exist" in out.reason


@pytest.mark.parametrize(
    "evidence,reason",
    [
        ([], "no evidence"),
        ([{"page": 0, "excerpt": "tenth studio", "stance": "supports"}], "too short"),
        ([{"page": 0, "excerpt": " ".join(["tenth"] * 61), "stance": "supports"}], "longer than"),
        (
            [{"page": 0, "excerpt": "tenth studio album\nby the English", "stance": "supports"}],
            "several lines",
        ),
    ],
)
def test_bad_evidence_is_dropped(evidence, reason):
    out = check_claim(raw(evidence=evidence), [page()], "x")
    assert isinstance(out, Dropped) and reason in out.reason


def test_lyrics_site_pages_are_refused_even_if_the_quote_is_real():
    lyric_page = page(url="https://genius.com/Pink-floyd-dogs-lyrics")
    out = check_claim(raw(), [lyric_page], "x")
    assert isinstance(out, Dropped) and "lyrics site" in out.reason
    assert is_lyric_domain("https://www.azlyrics.com/x") and not is_lyric_domain(
        "https://en.wikipedia.org"
    )


def test_multiline_body_is_dropped():
    out = check_claim(raw(body="line one\nline two"), [page()], "x")
    assert isinstance(out, Dropped) and "several lines" in out.reason


def test_track_claim_needs_a_track_number():
    out = check_claim(raw(subject="track"), [page()], "x")
    assert isinstance(out, Dropped) and "track number" in out.reason


def test_artist_intent_needs_a_named_speaker():
    out = check_claim(raw(type="artist_intent"), [page()], "x")
    assert isinstance(out, Dropped) and "speaker" in out.reason
    ok = check_claim(raw(type="artist_intent", author="Roger Waters"), [page()], "x")
    assert isinstance(ok, Candidate) and ok.author == "Roger Waters"


def test_unknown_values_from_the_model_are_dropped_not_crashed():
    out = check_claim(raw(type="gossip"), [page()], "x")
    assert isinstance(out, Dropped) and "invalid" in out.reason


def test_a_fetched_page_can_never_yield_a_primary_source():
    c = check_claim(raw(type="artist_intent", author="Roger Waters"), [page()], "x")
    assert all(s.tier != Tier.primary for s in c.sources)


# ---- the whole batch ------------------------------------------------------------------------


def test_check_all_assigns_ids_and_separates_dropped():
    result = check_all([raw(), raw(body="")], [page()])
    assert [c.id for c in result.candidates] == ["proposed-001"]
    assert len(result.dropped) == 1


def cand(body, n=None, url="https://x.test/a") -> Candidate:
    return Candidate(
        id="c",
        type=ClaimType.fact,
        body=body,
        subject="track" if n else "album",
        track_number=n,
        sources=[
            CandidateSource(
                url=url, title="T", kind="database", tier=Tier.tertiary, excerpt="a b c"
            )
        ],
    )


def test_duplicates_are_merged_and_keep_all_evidence():
    a = cand("The pig floated over Battersea power station in 1976", url="https://x.test/a")
    b = cand("The pig floated over Battersea power station in 1976.", url="https://x.test/b")
    kept, merged = merge_duplicates([a, b])
    assert len(kept) == 1 and merged == 1
    assert {s.url for s in kept[0].sources} == {"https://x.test/a", "https://x.test/b"}


def test_same_words_about_different_tracks_are_not_merged():
    kept, merged = merge_duplicates(
        [cand("Recorded in April 1976", 1), cand("Recorded in April 1976", 2)]
    )
    assert len(kept) == 2 and merged == 0


def test_claims_the_seed_already_has_are_dropped():
    kept, dropped = drop_existing(
        [cand("Recorded at Britannia Row in London in 1976"), cand("The sleeve shows a pig")],
        ["Recorded at the band's own Britannia Row studio in London, 1976"],
    )
    assert [c.body for c in kept] == ["The sleeve shows a pig"]
    assert dropped[0].reason == "already in the seed"
