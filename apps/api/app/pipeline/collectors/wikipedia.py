"""Wikipedia through its public API: article text, its external links, and the song articles.

Wikipedia is a tertiary source. We collect it because its text is verifiable, its reference list
points at the sources we really want (interviews, books, press), and it is free to reuse
(CC BY-SA; the page URL we store carries the revision id so a quote can be traced to a version).
"""

import json
import re

from app.pipeline.http import Fetcher, NotFound
from app.pipeline.models import Page

API = "https://en.wikipedia.org/w/api.php"
ARTICLE = "https://en.wikipedia.org/wiki/"
# Parentheticals that mark a music article (as opposed to the animal, the verb, a town...).
_MUSIC_HINTS = ("song", "single", "album", "instrumental", "band")


def track_key(title: str) -> str:
    """Compare track and article titles: 'Pigs on the Wing, Part One' == 'Pigs on the Wing'."""
    t = re.sub(r"\([^)]*\)", " ", title.lower())
    t = re.sub(r"[,:\-]?\s*part\s+(one|two|three|i{1,3}|\d)\b", " ", t)
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def _base_params(**extra) -> dict:
    return {"action": "query", "format": "json", "formatversion": "2", **extra}


class WikipediaCollector:
    def __init__(self, fetcher: Fetcher):
        self.fetcher = fetcher

    # ---- finding the album article ---------------------------------------------------------

    def find_album_title(self, album: str, artist: str) -> str | None:
        data = self.fetcher.get_json(
            API, _base_params(list="search", srsearch=f"{album} {artist} album", srlimit=5)
        )
        for hit in data["query"]["search"]:
            title = hit["title"]
            low = title.lower()
            if low.startswith(album.lower()) and ("album" in low or artist.lower() in low):
                return title
        return None

    # ---- one article -----------------------------------------------------------------------

    def article(self, title: str) -> Page | None:
        try:
            record = self.fetcher.fetch(
                API,
                _base_params(
                    prop="extracts|revisions",
                    explaintext=1,
                    exlimit=1,
                    redirects=1,
                    rvprop="ids|timestamp",
                    titles=title,
                ),
            )
        except NotFound:
            return None
        data = json.loads(record.text)
        pages = data["query"]["pages"]
        if not pages or pages[0].get("missing") or not pages[0].get("extract"):
            return None
        page = pages[0]
        revision = (page.get("revisions") or [{}])[0]
        oldid = revision.get("revid")
        url = ARTICLE + page["title"].replace(" ", "_")
        if oldid:
            url += f"?oldid={oldid}"
        return Page(
            url=url,
            title=page["title"],
            kind="wikipedia",
            fetched_at=record.fetched_at,
            text=page["extract"],
            meta={
                "pageid": page.get("pageid"),
                "revid": oldid,
                "revision_time": revision.get("timestamp"),
                "extlinks": self._listing(title, "extlinks", "extlinks", "url", ellimit="max"),
                "links": self._listing(
                    title, "links", "links", "title", pllimit="max", plnamespace=0
                ),
            },
        )

    def _listing(self, title: str, prop: str, key: str, field: str, **params) -> list[str]:
        out: list[str] = []
        cont: dict = {}
        for _ in range(10):  # a long article can span a few pages of results
            data = self.fetcher.get_json(
                API, _base_params(prop=prop, titles=title, redirects=1, **params, **cont)
            )
            pages = data["query"]["pages"]
            if pages:
                out += [item[field] for item in pages[0].get(key, [])]
            cont = data.get("continue") or {}
            cont = {k: v for k, v in cont.items() if k != "continue"}
            if not cont:
                break
        return out

    # ---- an album and its songs ------------------------------------------------------------

    def collect(
        self, album: str, artist: str, track_titles: list[str]
    ) -> tuple[list[Page], list[str]]:
        notes: list[str] = []
        title = self.find_album_title(album, artist)
        album_page = self.article(title) if title else None
        if album_page is None:
            return [], [f"No Wikipedia article found for '{album}' by {artist}."]
        pages = [album_page]
        seen = {album_page.title}

        links = album_page.meta["links"]
        for track in track_titles:
            page = self._song_page(track, artist, links)
            if page is None:
                notes.append(f"No Wikipedia article found for the song '{track}'.")
            elif page.title not in seen:
                seen.add(page.title)
                pages.append(page)
        return pages, notes

    def _song_page(self, track: str, artist: str, links: list[str]) -> Page | None:
        key = track_key(track)
        candidates = [link for link in links if track_key(link) == key]
        # Music-looking titles first: "Sheep (Pink Floyd song)" before the animal "Sheep".
        candidates.sort(
            key=lambda t: (
                0 if any(h in t.lower() for h in _MUSIC_HINTS) or artist.lower() in t.lower() else 1
            )
        )
        for title in candidates:
            page = self.article(title)
            # Whatever the title looks like, the article must be about this artist's song.
            if page and artist.lower() in page.text[:2000].lower():
                return page
        return None
