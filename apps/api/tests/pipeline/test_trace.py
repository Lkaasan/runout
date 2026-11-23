from datetime import UTC, datetime

import httpx
import pytest

from app.models.enums import ClaimType, SourceKind, Stance, Tier
from app.pipeline.cache import ResearchCache
from app.pipeline.http import Fetcher, FetchError, UnsafeURL, ensure_public
from app.pipeline.llm import ClaudeCodeBackend, LLMError
from app.pipeline.models import Candidate, CandidateSource, Page, Proposal
from app.pipeline.render import to_seed_documents, validate_documents
from app.pipeline.scoring import approvable
from app.pipeline.trace import check_page, targets, trace_claims
from tests.pipeline.test_extraction import FakeBackend

NOW = datetime.now(UTC)


def public(host, port):
    return [(2, 1, 6, "", ("93.184.216.34", port))]


def private(host, port):
    return [(2, 1, 6, "", ("10.0.0.5", port))]


# ---- keeping model-suggested addresses safe ------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com/x",
        "http://user:secret@example.com/x",
        "https://example.com:8080/x",
        "http://localhost/admin",
        "http://printer.local/x",
        "http://metadata.internal/x",
    ],
)
def test_unsafe_addresses_are_refused(url):
    with pytest.raises(UnsafeURL):
        ensure_public(url, resolver=public)


def test_hosts_that_resolve_to_private_addresses_are_refused():
    with pytest.raises(UnsafeURL, match="non-public"):
        ensure_public("https://innocent-looking.example/x", resolver=private)
    for ip in ("127.0.0.1", "169.254.169.254", "192.168.1.1", "::1"):
        with pytest.raises(UnsafeURL):
            ensure_public(f"http://{ip}/", resolver=lambda h, p, ip=ip: [(2, 1, 6, "", (ip, p))])


def test_public_addresses_pass():
    ensure_public("https://www.example.com/article", resolver=public)


def test_a_fetcher_with_a_real_client_checks_every_address(tmp_path, monkeypatch):
    monkeypatch.setattr("app.pipeline.http.socket.getaddrinfo", private)
    fetcher = Fetcher(ResearchCache(tmp_path))
    with pytest.raises(UnsafeURL):
        fetcher.get_text("https://sneaky.example/x")


def test_network_failures_become_fetch_errors_not_crashes(tmp_path):
    def boom(request):
        raise httpx.ConnectError("no route")

    fetcher = Fetcher(
        ResearchCache(tmp_path),
        client=httpx.Client(transport=httpx.MockTransport(boom)),
        respect_robots=False,
        sleep=lambda s: None,
    )
    with pytest.raises(FetchError, match="ConnectError"):
        fetcher.get_text("https://down.example/x")


# ---- the tools a backend is given -------------------------------------------------------------


def test_default_backend_has_no_tools_and_discovery_gets_only_web_tools():
    plain = ClaudeCodeBackend(claude_path="claude").command("S", {})
    assert plain[plain.index("--tools") + 1] == "" and "--allowedTools" not in plain

    web = ClaudeCodeBackend(claude_path="claude", tools=("WebSearch", "WebFetch")).command("S", {})
    assert web[web.index("--tools") + 1] == "WebSearch,WebFetch"
    allowed = web[web.index("--allowedTools") + 1 : web.index("--allowedTools") + 3]
    assert allowed == ["WebSearch", "WebFetch"]
    assert "--safe-mode" in web and "--bare" not in web


# ---- checking one page --------------------------------------------------------------------------

INTERVIEW = Page(
    url="https://guitarworld.example/interview",
    title="Gilmour interview",
    kind="web",
    fetched_at=NOW,
    text=(
        "Q: How did you build the harmonies? David Gilmour: I love the album; it was exciting "
        "and noisy and fun. We did three-part harmonies in some places."
    ),
)


def intent(id_="c", author="David Gilmour", body="Gilmour said he loved the album.") -> Candidate:
    return Candidate(
        id=id_,
        type=ClaimType.artist_intent,
        author=author,
        body=body,
        sources=[
            CandidateSource(
                url="https://en.wikipedia.org/wiki/Animals",
                title="Animals",
                kind=SourceKind.database,
                tier=Tier.tertiary,
                excerpt="Gilmour said he loved the album",
            )
        ],
    )


def answer(**kw) -> dict:
    base = {
        "found": True,
        "excerpt": "I love the album; it was exciting and noisy and fun.",
        "original_publication": True,
        "source_kind": "interview",
        "publication": "Guitar World, February 1993",
        "why": "It is the interview itself.",
    }
    return {**base, **kw}


def test_a_verbatim_first_person_quote_from_the_original_is_proposed_not_declared_primary():
    out = check_page(FakeBackend([answer()]), intent(), INTERVIEW)
    assert isinstance(out, CandidateSource)
    assert out.primary_proposed and out.tier == Tier.secondary  # a person makes it primary
    assert out.kind == SourceKind.interview and "Guitar World" in out.proposed_why


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"found": False}, "does not contain"),
        (
            {"excerpt": "I adored the album and it was thrilling and loud and fun."},
            "not on the page",
        ),
        ({"excerpt": "We did three-part harmonies in some places"}, None),  # fine: first person
        ({"excerpt": "it was exciting and noisy and fun"}, "first-person"),
        ({"original_publication": False}, "not the original"),
        ({"excerpt": "I love"}, "wrong length"),
    ],
)
def test_pages_that_do_not_qualify_say_why(change, reason):
    out = check_page(FakeBackend([answer(**change)]), intent(), INTERVIEW)
    if reason is None:
        assert isinstance(out, CandidateSource)
    else:
        assert isinstance(out, str) and reason in out


def test_the_speaker_must_be_named_on_the_page():
    page = INTERVIEW.model_copy(update={"text": INTERVIEW.text.replace("Gilmour", "Someone")})
    out = check_page(FakeBackend([answer()]), intent(), page)
    assert isinstance(out, str) and "never names" in out


def test_encyclopedias_are_never_the_original():
    wiki = INTERVIEW.model_copy(update={"url": "https://en.wikipedia.org/wiki/X"})
    out = check_page(FakeBackend([answer()]), intent(), wiki)
    assert isinstance(out, str) and "encyclopedia" in out


def test_a_model_failure_is_a_reason_not_a_crash():
    out = check_page(FakeBackend([LLMError("limit")]), intent(), INTERVIEW)
    assert isinstance(out, str) and "limit" in out


def test_a_proposed_primary_does_not_make_a_claim_approvable():
    claim = intent()
    claim.sources.append(check_page(FakeBackend([answer()]), claim, INTERVIEW))
    assert not approvable(claim)  # still waiting for a person to confirm


# ---- the whole trace ----------------------------------------------------------------------------


def fetcher_for(tmp_path, html: str, public_only: bool = False) -> Fetcher:
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, text=html)

    return Fetcher(
        ResearchCache(tmp_path),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=lambda s: None,
        public_only=public_only,
    )


ARTICLE = (
    "<html><head><title>Gilmour interview</title></head><body><article><h1>Gilmour interview</h1>"
    "<p>David Gilmour: I love the album; it was exciting and noisy and fun. "
    + "More. " * 60
    + "</p></article></body></html>"
)


def test_targets_are_artist_intent_claims_without_a_proposed_primary():
    done = intent("a")
    done.sources[0].primary_proposed = True
    other = Candidate(id="f", type=ClaimType.fact, body="A fact", sources=[])
    no_speaker = Candidate(id="n", type=ClaimType.artist_intent, body="x", author=None)
    assert [c.id for c in targets([done, intent("b"), other, no_speaker])] == ["b"]


def test_trace_finds_checks_and_proposes_the_original(tmp_path):
    claims = [intent("a")]
    discover = FakeBackend(
        [
            {
                "leads": [
                    {"url": "https://en.wikipedia.org/wiki/Dogs", "why": "no"},
                    {"url": "https://guitarworld.example/interview", "why": "the interview"},
                ]
            }
        ]
    )
    check = FakeBackend([answer()])
    result = trace_claims(discover, check, claims, set(), fetcher_for(tmp_path, ARTICLE), limit=5)
    assert result.examined == 1 and result.proposed == [
        ("a", "https://guitarworld.example/interview")
    ]
    assert result.leads_refused == 1  # the Wikipedia address
    added = claims[0].sources[-1]
    assert added.primary_proposed and added.tier == Tier.secondary
    assert "PRIMARY PROPOSED" in claims[0].notes[0]


def test_trace_skips_known_pages_unsafe_addresses_and_empty_answers(tmp_path):
    claims = [intent("a"), intent("b", body="Gilmour said something else entirely here.")]
    discover = FakeBackend(
        [
            {
                "leads": [
                    {"url": "http://localhost:8000/admin", "why": "x"},
                    {"url": "https://known.example/page", "why": "already read"},
                ]
            },
            {"leads": []},
        ]
    )
    result = trace_claims(
        discover,
        FakeBackend([]),
        claims,
        {"https://known.example/page"},
        fetcher_for(tmp_path, ARTICLE, public_only=True),
    )
    assert result.proposed == [] and result.leads_refused == 1 and result.leads_fetched == 0
    assert all(not c.sources[-1].primary_proposed for c in claims)


def test_trace_respects_the_limit_and_survives_a_failed_search(tmp_path):
    claims = [
        intent(str(i), body=f"Gilmour said thing number {i} in the interview.") for i in range(5)
    ]
    discover = FakeBackend([LLMError("limit hit"), {"leads": []}])
    result = trace_claims(
        discover, FakeBackend([]), claims, set(), fetcher_for(tmp_path, ARTICLE), limit=2
    )
    assert result.examined == 2
    assert any("limit hit" in n for n in result.notes)


# ---- showing it to a person ----


def test_proposed_primaries_are_flagged_in_the_proposal_file_and_stay_secondary():
    claim = intent("a")
    claim.sources.append(check_page(FakeBackend([answer()]), claim, INTERVIEW))
    sources, claims = to_seed_documents(Proposal(slug="x", candidates=[claim]))
    proposed = [s for s in sources if "PROPOSED PRIMARY" in s["title"]]
    assert len(proposed) == 1 and proposed[0]["tier"] == "secondary"
    assert validate_documents(sources, claims) == []
    assert Stance.supports.value == claims[0]["sources"][-1]["stance"]


def test_a_page_already_cited_can_be_the_original_so_no_search_is_needed(tmp_path):
    claim = intent("a")
    claim.sources[0].url = INTERVIEW.url
    claim.sources[0].title = INTERVIEW.title
    discover = FakeBackend([])  # must not be asked
    result = trace_claims(
        discover,
        FakeBackend([answer()]),
        [claim],
        {INTERVIEW.url},
        fetcher_for(tmp_path, ARTICLE),
        pages=[INTERVIEW],
    )
    assert result.own_pages == 1 and result.proposed == [("a", INTERVIEW.url)]
    assert discover.prompts == []
    assert len(claim.sources) == 1 and claim.sources[0].primary_proposed  # marked, not duplicated
    assert claim.sources[0].tier != Tier.primary


def test_if_the_cited_page_is_not_the_original_the_search_still_runs(tmp_path):
    claim = intent("a")
    claim.sources[0].url = INTERVIEW.url
    discover = FakeBackend([{"leads": []}])
    check = FakeBackend([answer(original_publication=False)])
    result = trace_claims(
        discover, check, [claim], {INTERVIEW.url}, fetcher_for(tmp_path, ARTICLE), pages=[INTERVIEW]
    )
    assert result.proposed == [] and len(discover.prompts) == 1
    assert any("not the original" in n for n in result.notes)
