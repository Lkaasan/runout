import json
from datetime import UTC, datetime

import httpx
import pytest

from app.models.enums import ClaimType, SourceKind, Stance, Tier
from app.pipeline.cache import ResearchCache
from app.pipeline.checks import classify
from app.pipeline.collectors.web import WebCollector, html_to_text, load_research_urls
from app.pipeline.conflicts import find_conflicts
from app.pipeline.http import Fetcher
from app.pipeline.llm import CachingBackend, LLMError, LLMUsage
from app.pipeline.models import Candidate, CandidateSource, Page
from app.pipeline.run import run_extraction
from app.pipeline.verifier import verify_candidates
from app.pipeline.verifier_eval import plant_errors, run_eval
from tests.pipeline.test_extraction import FakeBackend, bundle, claim

NOW = datetime.now(UTC)
WIKI = Page(
    url="https://en.wikipedia.org/wiki/Animals",
    title="Animals",
    kind="wikipedia",
    fetched_at=NOW,
    text="The pig, nicknamed Algie, was 12 metres long. Waters said the album was a sketch.",
)
PRESS = Page(
    url="https://americansongwriter.com/cover",
    title="Cover story",
    kind="web",
    fetched_at=NOW,
    text="The inflatable pig was about 30 feet long and broke loose on the second day.",
)


def cand(id_, body, type_=ClaimType.fact, author=None, page=WIKI, excerpt=None) -> Candidate:
    return Candidate(
        id=id_,
        type=type_,
        body=body,
        author=author,
        sources=[
            CandidateSource(
                url=page.url,
                title=page.title,
                kind=SourceKind.database,
                tier=Tier.tertiary,
                excerpt=excerpt or "was 12 metres long",
            )
        ],
    )


def verdict(id_, verdict="supported", issue="", type_ok=True, speaker_ok=True) -> dict:
    return {
        "id": id_,
        "verdict": verdict,
        "issue": issue,
        "type_ok": type_ok,
        "speaker_ok": speaker_ok,
    }


# ---- web pages ---------------------------------------------------------------------------------

HTML = """<html><head><title>Site | Cover story</title></head><body>
<nav>Home Menu Subscribe</nav><header>Logo</header>
<article><h1>All hell broke loose</h1>
<p>The inflatable pig was about 30 feet long.</p>
<p>It broke loose on the second day of the shoot, drifting towards the airport.</p>
<script>var x = 1;</script>
<p>A third paragraph of the story with enough words to count as real article text.</p></article>
<footer>Copyright</footer></body></html>"""


def test_inline_markup_does_not_add_spaces_that_break_quotes():
    html = (
        "<article><p>It was called <em>Animals</em>, and the title track, "
        '<a href="/x">Dogs</a>, ran for 17 minutes. ' + "More text here. " * 20 + "</p></article>"
    )
    _, text = html_to_text(html)
    assert "It was called Animals, and the title track, Dogs, ran for 17 minutes." in text


def test_html_to_text_keeps_the_article_and_drops_the_furniture():
    title, text = html_to_text(HTML)
    assert title == "All hell broke loose"
    assert "about 30 feet long" in text and "drifting towards the airport" in text
    assert "Subscribe" not in text and "Copyright" not in text and "var x" not in text


def test_web_collector_reads_cached_pages_politely(tmp_path):
    big = HTML.replace("</article>", "<p>" + "More reporting. " * 30 + "</p></article>")
    calls = []

    def handler(request):
        calls.append(str(request.url))
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, text=big)

    cache = ResearchCache(tmp_path)
    fetcher = Fetcher(
        cache, client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda s: None
    )
    pages, notes = WebCollector(fetcher).collect(["https://americansongwriter.com/cover"])
    assert notes == [] and pages[0].kind == "web" and pages[0].title == "All hell broke loose"
    WebCollector(fetcher).collect(["https://americansongwriter.com/cover"])
    assert len([c for c in calls if c.endswith("/cover")]) == 1  # second read came from the cache


def test_research_urls_file(tmp_path):
    (tmp_path / "animals").mkdir()
    assert load_research_urls(tmp_path, "animals") == []
    (tmp_path / "animals" / "research.yaml").write_text("urls:\n  - https://a.test/x\n")
    assert load_research_urls(tmp_path, "animals") == ["https://a.test/x"]
    (tmp_path / "animals" / "research.yaml").write_text("urls:\n  - ftp://a.test/x\n")
    with pytest.raises(ValueError):
        load_research_urls(tmp_path, "animals")


def test_classify_by_domain_and_never_primary():
    assert classify(WIKI) == (SourceKind.database, Tier.tertiary)
    assert classify(PRESS) == (SourceKind.press, Tier.secondary)
    unknown = PRESS.model_copy(update={"url": "https://some-blog.example/post"})
    assert classify(unknown) == (SourceKind.press, Tier.tertiary)
    assert all(classify(p)[1] != Tier.primary for p in (WIKI, PRESS, unknown))


# ---- verifier ----------------------------------------------------------------------------------


def test_verifier_drops_unsupported_and_wrong_speaker_and_notes_the_rest():
    claims = [
        cand("a", "The pig was 12 metres long."),
        cand("b", "The pig was 20 metres long."),
        cand("c", "Gilmour said the album was a sketch.", ClaimType.artist_intent, "Gilmour"),
        cand("d", "The pig proved the best stunt ever."),
        cand("e", "Waters said the album was a sketch.", ClaimType.artist_intent, "Waters"),
    ]
    backend = FakeBackend(
        [
            {
                "verdicts": [
                    verdict("a"),
                    verdict("b", "unsupported", "page says 12"),
                    verdict("c", speaker_ok=False),
                    verdict("d", "overstated", "'proved the best' is not in the page"),
                    verdict("e", type_ok=False, issue="reads like a fact"),
                ]
            }
        ]
    )
    result = verify_candidates(backend, claims, [WIKI])
    assert [c.id for c in result.kept] == ["a", "d", "e"]
    reasons = " | ".join(d.reason for d in result.dropped)
    assert "unsupported" in reasons and "does not attribute" in reasons
    assert result.kept[1].notes[0].startswith("Overstated")
    assert "Type may be wrong" in result.kept[2].notes[0]
    assert result.flagged == 4


def test_a_missing_verdict_is_kept_but_marked_unchecked():
    claims = [cand("a", "The pig was 12 metres long.")]
    result = verify_candidates(FakeBackend([{"verdicts": []}]), claims, [WIKI])
    assert [c.id for c in result.kept] == ["a"]
    assert result.kept[0].notes[0].startswith("Not verified")


def test_a_model_failure_never_silently_trusts_claims():
    result = verify_candidates(FakeBackend([LLMError("limit hit")]), [cand("a", "x y z")], [WIKI])
    assert result.kept[0].notes and "limit hit" in result.notes[0]


def test_verifier_batches_by_the_page_a_claim_cites():
    backend = FakeBackend([{"verdicts": []}, {"verdicts": []}])
    claims = [cand("a", "one two three"), cand("b", "four five six", page=PRESS)]
    verify_candidates(backend, claims, [WIKI, PRESS])
    assert len(backend.prompts) == 2


# ---- conflicts ---------------------------------------------------------------------------------


def test_a_real_disagreement_becomes_a_contradicting_source():
    claim = cand("a", "The pig was 12 metres long.")
    backend = FakeBackend(
        [
            {
                "contradictions": [
                    {
                        "claim_id": "a",
                        "explanation": "this page says about 30 feet",
                        "excerpt": "The inflatable pig was about 30 feet long",
                    }
                ]
            }
        ]
    )
    result = find_conflicts(backend, [claim], [WIKI, PRESS])
    assert result.added == 1
    contra = [s for s in claim.sources if s.stance == Stance.contradicts]
    assert contra[0].url == PRESS.url and contra[0].tier == Tier.secondary
    assert "Disputed by Cover story" in claim.notes[0]


def test_an_invented_contradiction_quote_is_discarded():
    claim = cand("a", "The pig was 12 metres long.")
    backend = FakeBackend(
        [
            {
                "contradictions": [
                    {
                        "claim_id": "a",
                        "explanation": "x",
                        "excerpt": "the pig was 99 feet tall and purple",
                    }
                ]
            }
        ]
    )
    result = find_conflicts(backend, [claim], [WIKI, PRESS])
    assert result.added == 0 and result.discarded == 1
    assert len(claim.sources) == 1


def test_a_page_is_not_asked_about_claims_it_wrote():
    claim = cand("a", "The pig was 12 metres long.")  # cites WIKI
    backend = FakeBackend([{"contradictions": []}])
    find_conflicts(backend, [claim], [WIKI, PRESS])
    assert len(backend.prompts) == 1 and "Cover story" in backend.prompts[0]  # only PRESS asked


def test_contradicted_claims_cannot_be_auto_approved():
    from app.pipeline.scoring import approvable

    claim = cand("a", "The pig was 12 metres long.")
    assert approvable(claim)
    claim.sources.append(
        CandidateSource(
            url=PRESS.url,
            title="Cover story",
            kind=SourceKind.press,
            tier=Tier.secondary,
            stance=Stance.contradicts,
            excerpt="about 30 feet long",
        )
    )
    assert not approvable(claim)


# ---- the whole run -----------------------------------------------------------------------------


def run_pages() -> list[Page]:
    return [WIKI, PRESS]


def test_run_extracts_verifies_and_finds_the_conflict_end_to_end():
    wiki_claim = claim(0, "was 12 metres long", "The pig was 12 metres long.")
    press_claim = claim(1, "was about 30 feet long", "The pig was about 30 feet long.")
    backend = FakeBackend(
        [
            {"claims": [wiki_claim]},  # extract from wiki
            {"claims": [press_claim]},  # extract from press
            {"verdicts": [verdict("proposed-001")]},  # verify wiki claims
            {"verdicts": [verdict("proposed-002")]},  # verify press claims
            {
                "contradictions": [
                    {
                        "claim_id": "proposed-002",
                        "explanation": "12 m",
                        "excerpt": "was 12 metres long",
                    }
                ]
            },
            {
                "contradictions": [
                    {
                        "claim_id": "proposed-001",
                        "explanation": "30 ft",
                        "excerpt": "was about 30 feet long",
                    }
                ]
            },
        ]
    )
    result = run_extraction(bundle(), run_pages(), backend, skip_existing=False)
    assert len(result.proposal.candidates) == 2
    for c in result.proposal.candidates:
        assert {s.stance for s in c.sources} == {Stance.supports, Stance.contradicts}
    assert result.conflicts.added == 2 and "conflicts: 2" in result.summary()


def test_steps_can_be_switched_off():
    backend = FakeBackend([{"claims": [claim(0, "was 12 metres long")]}, {"claims": []}])
    result = run_extraction(
        bundle(), run_pages(), backend, skip_existing=False, verify=False, conflicts=False
    )
    assert result.verified is None and result.conflicts is None and len(backend.prompts) == 2


# ---- planted errors ----------------------------------------------------------------------------


def test_plant_errors_damages_every_second_claim_deterministically():
    claims = [
        cand("a", "Recorded in 1976 at Britannia Row."),
        cand("b", "Waters wrote the lyrics in 1976."),
        cand("c", "Mason played drums."),
        cand("d", "Gilmour sang the first half."),
    ]
    damaged, planted = plant_errors(claims)
    assert set(planted) == {"b", "d"}
    assert damaged[0].body == claims[0].body and damaged[2].body == claims[2].body  # untouched
    assert damaged[1].body != claims[1].body and damaged[3].body != claims[3].body
    assert plant_errors(claims)[1] == planted  # same every time
    assert claims[1].body == "Waters wrote the lyrics in 1976."  # the originals are not changed


def test_eval_counts_caught_errors_and_false_alarms():
    claims = [cand("a", "Waters wrote it in 1976."), cand("b", "Waters wrote it in 1976, he said.")]
    damaged, planted = plant_errors(claims)
    assert set(planted) == {"b"}

    class Judge(FakeBackend):
        def run_structured(self, *, system, prompt, schema):
            return {
                "verdicts": [
                    verdict("a", "overstated", "hmm"),
                    verdict("b", "unsupported", "changed"),
                ]
            }

    report = run_eval(Judge([]), claims, [WIKI])
    assert (report.planted, report.caught) == (1, 1)
    assert (report.untouched, report.false_alarms) == (1, 1)
    assert "caught" in report.summary()


# ---- saved answers -----------------------------------------------------------------------------


def test_caching_backend_pays_once_per_distinct_prompt(tmp_path):
    inner = FakeBackend([{"claims": [1]}, {"claims": [2]}])
    inner.usage = LLMUsage()
    cached = CachingBackend(inner, tmp_path)
    first = cached.run_structured(system="s", prompt="p", schema={})
    again = cached.run_structured(system="s", prompt="p", schema={})
    other = cached.run_structured(system="s", prompt="p2", schema={})
    assert first == again == {"claims": [1]} and other == {"claims": [2]}
    assert cached.hits == 1 and len(inner.prompts) == 2
    fresh = CachingBackend(FakeBackend([{"claims": [3]}]), tmp_path, fresh=True)
    assert fresh.run_structured(system="s", prompt="p", schema={}) == {"claims": [3]}
    assert json.loads(next((tmp_path / "llm").glob("*.json")).read_text())  # stored as JSON
