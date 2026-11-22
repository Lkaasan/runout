"""Deterministic checks on what a model proposes. None of these call a model.

The model proposes; these checks decide what survives. The most important one is the excerpt
check: every claim must quote, word for word, a passage that really is in a page we fetched.
A quote we cannot find is a quote the model made up, and the claim is dropped.
"""

import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

from app.models.enums import ClaimType, SourceKind, Tier
from app.pipeline.models import Candidate, CandidateSource, Page
from app.pipeline.scoring import similarity

MIN_EXCERPT_WORDS = 3
MAX_EXCERPT_WORDS = 60
MAX_BODY_CHARS = 600

# Sites that publish lyrics. Never a source for us, whatever a model says.
LYRIC_DOMAINS = (
    "genius.com",
    "azlyrics.com",
    "musixmatch.com",
    "lyrics.com",
    "songlyrics.com",
    "metrolyrics.com",
    "lyricfind.com",
    "lyricsfreak.com",
)

# What a fetched page is worth. Primary is never granted from a fetched page: a page is a
# tertiary or secondary account of what someone said, even when it quotes them. Primary needs
# the original source (step 4).
DOMAIN_RULES = {
    "loudersound.com": (SourceKind.press, Tier.secondary),
    "americansongwriter.com": (SourceKind.press, Tier.secondary),
    "faroutmagazine.co.uk": (SourceKind.press, Tier.secondary),
    "songfacts.com": (SourceKind.database, Tier.tertiary),
}


def classify(page: Page) -> tuple[SourceKind, Tier]:
    """Source kind and tier for a page, from what it is and where it came from."""
    if page.kind in ("wikipedia", "musicbrainz"):
        return SourceKind.database, Tier.tertiary
    host = (urlparse(page.url).hostname or "").removeprefix("www.")
    for domain, rule in DOMAIN_RULES.items():
        if host == domain or host.endswith("." + domain):
            return rule
    return SourceKind.press, Tier.tertiary  # an unknown site is not trusted as secondary


_TRANSLATE = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "“": '"',
        "”": '"',
        "–": "-",
        "—": "-",
        "−": "-",
        " ": " ",
    }
)


def normalize(text: str) -> str:
    """Make quotes, dashes and whitespace comparable. Case and words are left alone."""
    return re.sub(r"\s+", " ", text.translate(_TRANSLATE)).strip()


def word_count(text: str) -> int:
    return len(text.split())


def excerpt_in_page(excerpt: str, page_text: str) -> bool:
    """True if the excerpt appears word for word in the page (typography and spacing aside)."""
    needle = normalize(excerpt)
    return bool(needle) and needle in normalize(page_text)


def is_lyric_domain(url: str | None) -> bool:
    host = (urlparse(url).hostname or "").removeprefix("www.") if url else ""
    return any(host == d or host.endswith("." + d) for d in LYRIC_DOMAINS)


_SPEECH = (
    r"said|says|told|wrote|recalled|explained|stated|confirmed|described|noted|claimed|"
    r"revealed|remarked|added|admitted|insisted|reflected|commented|called|thought|felt"
)
_SPEAKER = re.compile(rf"^((?:[A-Z][\w'.\-]+)(?: [A-Z][\w'.\-]+){{0,2}}) (?:{_SPEECH})\b")


def infer_speaker(body: str, page_text: str) -> str | None:
    """ "Waters said ..." -> "Waters", but only when that name appears on the page."""
    match = _SPEAKER.match(body.strip())
    if not match:
        return None
    name = match.group(1)
    return name if name in normalize(page_text) else None


# ---- turning what a model said into a checked Candidate ---------------------------------------


@dataclass
class Dropped:
    reason: str
    body: str


@dataclass
class CheckResult:
    candidates: list[Candidate] = field(default_factory=list)
    dropped: list[Dropped] = field(default_factory=list)


def check_claim(raw: dict, pages: list[Page], claim_id: str) -> Candidate | Dropped:
    """Validate one raw claim from a model against the pages. Returns a Candidate or why not."""
    body = (raw.get("body") or "").strip()
    if not body:
        return Dropped("empty body", "")
    if len(body) > MAX_BODY_CHARS:
        return Dropped(f"body longer than {MAX_BODY_CHARS} characters", body[:80])
    if "\n" in body:
        return Dropped("body spans several lines (looks like lyrics or a list)", body[:80])

    evidence = raw.get("evidence") or []
    if not evidence:
        return Dropped("no evidence given", body)

    sources: list[CandidateSource] = []
    for ev in evidence:
        index = ev.get("page")
        if not isinstance(index, int) or not 0 <= index < len(pages):
            return Dropped(f"evidence points at page {index!r}, which does not exist", body)
        page = pages[index]
        excerpt = (ev.get("excerpt") or "").strip()
        words = word_count(excerpt)
        if words < MIN_EXCERPT_WORDS:
            return Dropped("excerpt too short to verify", body)
        if words > MAX_EXCERPT_WORDS:
            return Dropped(f"excerpt longer than {MAX_EXCERPT_WORDS} words", body)
        if "\n" in excerpt:
            return Dropped("excerpt spans several lines (looks like lyrics)", body)
        if is_lyric_domain(page.url):
            return Dropped("source is a lyrics site", body)
        if not excerpt_in_page(excerpt, page.text):
            return Dropped("excerpt is not in the page it cites (invented or altered)", body)
        kind, tier = classify(page)
        sources.append(
            CandidateSource(
                url=page.url,
                title=page.title,
                kind=kind,
                tier=tier,
                stance=ev.get("stance") or "supports",
                excerpt=excerpt,
                locator=ev.get("locator"),
            )
        )

    try:
        candidate = Candidate(
            id=claim_id,
            subject=raw.get("subject") or "album",
            track_number=raw.get("track_number"),
            type=raw.get("type"),
            depth=raw.get("depth") or "listen",
            phase=raw.get("phase"),
            body=body,
            body_long=(raw.get("body_long") or None),
            author=(raw.get("author") or None),
            sources=sources,
        )
    except ValueError as exc:  # pydantic's ValidationError is a ValueError
        return Dropped(f"invalid claim: {str(exc).splitlines()[0]}", body)

    if candidate.subject == "track" and candidate.track_number is None:
        return Dropped("track claim without a track number", body)
    if candidate.type == ClaimType.artist_intent and not candidate.author:
        # The model left the speaker blank although the claim says who spoke ("Waters said ...").
        # Recover the name only if it is really on the cited page; otherwise drop the claim.
        speaker = infer_speaker(body, pages[raw["evidence"][0]["page"]].text)
        if speaker is None:
            return Dropped("artist intent without a named speaker", body)
        candidate.author = speaker
    return candidate


# ---- duplicates --------------------------------------------------------------------------------

DUPLICATE_THRESHOLD = 0.6


def merge_duplicates(candidates: list[Candidate]) -> tuple[list[Candidate], int]:
    """Fold near-identical claims (found on several pages) into one that cites all the evidence."""
    kept: list[Candidate] = []
    merged = 0
    for c in candidates:
        twin = next(
            (
                k
                for k in kept
                if k.subject == c.subject
                and k.track_number == c.track_number
                and similarity(k.body, c.body) >= DUPLICATE_THRESHOLD
            ),
            None,
        )
        if twin is None:
            kept.append(c)
            continue
        merged += 1
        have = {(s.url, s.excerpt) for s in twin.sources}
        twin.sources += [s for s in c.sources if (s.url, s.excerpt) not in have]
    return kept, merged


def drop_existing(
    candidates: list[Candidate], existing_bodies: list[str]
) -> tuple[list[Candidate], list[Dropped]]:
    """Drop proposals that say what the album's seed already says."""
    kept, dropped = [], []
    for c in candidates:
        if any(similarity(c.body, e) >= DUPLICATE_THRESHOLD for e in existing_bodies):
            dropped.append(Dropped("already in the seed", c.body))
        else:
            kept.append(c)
    return kept, dropped


def check_all(raw_claims: list[dict], pages: list[Page]) -> CheckResult:
    """Check every raw claim from the model; ids are assigned here, never by the model."""
    result = CheckResult()
    for n, raw in enumerate(raw_claims, start=1):
        outcome = check_claim(raw, pages, claim_id=f"proposed-{n:03d}")
        if isinstance(outcome, Dropped):
            result.dropped.append(outcome)
        else:
            result.candidates.append(outcome)
    return result
