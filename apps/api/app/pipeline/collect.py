"""Step 1 of the information finder: gather source text with no AI involved.

Reads the album and track titles from the seed, collects from MusicBrainz and Wikipedia, and
stores the assembled pages for later stages. Everything fetched is cached, so a second run
makes no network calls.
"""

from dataclasses import dataclass, field

from app.pipeline.cache import ResearchCache
from app.pipeline.collectors.musicbrainz import MusicBrainzCollector
from app.pipeline.collectors.wikipedia import WikipediaCollector
from app.pipeline.http import Fetcher, FetchError
from app.pipeline.models import Page
from app.services.seed_loader import AlbumBundle


@dataclass
class CollectReport:
    slug: str
    pages: list[Page] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    network_calls: int = 0
    cache_hits: int = 0

    def summary(self) -> str:
        lines = [f"Collected {len(self.pages)} page(s) for '{self.slug}':"]
        for p in self.pages:
            extra = ""
            if p.kind == "wikipedia":
                extra = f", {len(p.meta.get('extlinks', []))} external links"
            lines.append(f"  [{p.kind}] {p.title} - {len(p.text):,} characters{extra}")
        lines += [f"  note: {n}" for n in self.notes]
        lines.append(
            f"Network requests: {self.network_calls}, served from cache: {self.cache_hits}"
        )
        return "\n".join(lines)


def collect_album(bundle: AlbumBundle, fetcher: Fetcher, cache: ResearchCache) -> CollectReport:
    album, artist = bundle.album.title, bundle.album.artist.name
    titles = [t.title for t in bundle.tracks]
    report = CollectReport(slug=bundle.album.slug)
    start_calls, start_hits = fetcher.network_calls, fetcher.cache_hits

    for name, run in (
        ("MusicBrainz", lambda: MusicBrainzCollector(fetcher).collect(album, artist)),
        ("Wikipedia", lambda: WikipediaCollector(fetcher).collect(album, artist, titles)),
    ):
        try:
            pages, notes = run()
        except FetchError as exc:
            report.notes.append(f"{name} unavailable: {exc}")
            continue
        report.pages += pages
        report.notes += notes

    cache.put_pages(bundle.album.slug, report.pages)
    report.network_calls = fetcher.network_calls - start_calls
    report.cache_hits = fetcher.cache_hits - start_hits
    return report
