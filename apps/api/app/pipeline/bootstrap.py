"""Starting research on an album nobody has written seed files for yet.

The finder works from an album's seed folder (title, artist, track list). For a new or obscure
album there is no folder, so `init` builds a skeleton from what is publicly structured:

- the schema.org `MusicAlbum` data that Apple Music and Bandcamp pages publish (title, artist,
  release date, every track with its length, and the Apple Music ids the player needs),
- the album's Wikipedia article, when it has one, whose reference list becomes the first list of
  pages to read (`research.yaml`).

Nothing is invented: a skeleton has no claims at all. It is only the frame the finder fills in.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import yaml
from bs4 import BeautifulSoup

# Hosts that are shops, streaming pages, aggregators or archives of the same page, not articles.
NOT_ARTICLES = (
    "web.archive.org",
    "archive.org",
    "archive.is",
    "apple.com",
    "bandcamp.com",
    "qobuz.com",
    "spotify.com",
    "amazon.",
    "youtube.com",
    "youtu.be",
    "metacritic.com",
    "allmusic.com",
    "discogs.com",
    "musicbrainz.org",
    "wikipedia.org",
    "wikimedia.org",
    "wikidata.org",
    "instagram.com",
    "facebook.com",
    "twitter.com",
    "x.com",
    "tiktok.com",
    "genius.com",
)
MAX_RESEARCH_URLS = 14


@dataclass
class TrackInfo:
    number: int
    title: str
    duration_ms: int | None = None
    apple_music_id: str | None = None


@dataclass
class AlbumInfo:
    title: str
    artist: str
    release_date: str | None = None
    apple_music_id: str | None = None
    artist_apple_music_id: str | None = None
    artwork_url: str | None = None
    tracks: list[TrackInfo] = field(default_factory=list)
    source_url: str = ""


def iso_duration_ms(value: str | None) -> int | None:
    """'PT3M56S' (Apple) and 'P00H03M10S' (Bandcamp) -> milliseconds."""
    if not value:
        return None
    m = re.fullmatch(r"P(?:T)?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?", value.strip())
    if not m or not any(m.groups()):
        return None
    h, mi, s = (float(g) if g else 0 for g in m.groups())
    return round((h * 3600 + mi * 60 + s) * 1000)


def _apple_id(url: str | None) -> str | None:
    match = re.search(r"/(\d{6,})(?:\?|$)", url or "")
    return match.group(1) if match else None


def _artist(raw) -> tuple[str, str | None]:
    entry = raw[0] if isinstance(raw, list) and raw else raw
    if isinstance(entry, dict):
        return entry.get("name", ""), _apple_id(entry.get("url"))
    return (entry or ""), None


def _iso_date(value: str | None) -> str | None:
    """'2026-08-21' or '21 Aug 2026 00:00:00 GMT' -> '2026-08-21'."""
    if not value:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return value
    from email.utils import parsedate_to_datetime

    try:
        return parsedate_to_datetime(value.replace("GMT", "+0000")).date().isoformat()
    except (TypeError, ValueError):
        return None


def _square_artwork(url: str | None) -> str | None:
    if not url:
        return None
    # Apple serves a size in the last path segment; ask for a square one.
    return re.sub(r"/\d+x\d+[a-z]*\.(jpg|png)$", r"/600x600bb.\1", url)


def parse_music_album(html: str, url: str) -> AlbumInfo | None:
    """Read a schema.org MusicAlbum block (Apple Music, Bandcamp) from a page."""
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.get_text())
        except json.JSONDecodeError:
            continue
        if data.get("@type") != "MusicAlbum" or not data.get("name"):
            continue
        artist, artist_id = _artist(data.get("byArtist"))
        raw_tracks = data.get("tracks") or data.get("track") or []
        if isinstance(raw_tracks, dict):  # Bandcamp: an ItemList of ListItems
            raw_tracks = [e.get("item", {}) for e in raw_tracks.get("itemListElement", [])]
        tracks = [
            TrackInfo(
                number=i,
                title=t.get("name", ""),
                duration_ms=iso_duration_ms(t.get("duration")),
                apple_music_id=_apple_id(t.get("url")) if "apple.com" in url else None,
            )
            for i, t in enumerate(raw_tracks, start=1)
            if t.get("name")
        ]
        if not tracks or not artist:
            continue
        is_apple = "apple.com" in url
        image = data.get("image")
        return AlbumInfo(
            title=data["name"],
            artist=artist,
            release_date=_iso_date(data.get("datePublished")),
            apple_music_id=_apple_id(url) if is_apple else None,
            artist_apple_music_id=artist_id if is_apple else None,
            artwork_url=_square_artwork(image) if is_apple else image,
            tracks=tracks,
            source_url=url,
        )
    return None


def structured_page_candidates(extlinks: list[str]) -> list[str]:
    """Links in a Wikipedia article that are likely to carry a track list, best first."""
    apple = [u for u in extlinks if "music.apple.com" in u and "/album/" in u]
    bandcamp = [u for u in extlinks if "bandcamp.com/album/" in u]
    return apple + bandcamp


def pick_research_urls(extlinks: list[str], limit: int = MAX_RESEARCH_URLS) -> list[str]:
    """The article's own references that look like press or interviews, deduplicated."""
    seen: set[str] = set()
    out: list[str] = []
    for url in extlinks:
        parts = urlparse(url)
        host = (parts.hostname or "").removeprefix("www.")
        if parts.scheme not in ("http", "https") or any(h in host for h in NOT_ARTICLES):
            continue
        key = f"{host}{parts.path.rstrip('/')}"
        if key in seen:
            continue
        seen.add(key)
        out.append(url.replace("http://", "https://", 1))
        if len(out) >= limit:
            break
    return out


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _mmss(ms: int | None) -> str | None:
    if not ms:
        return None
    total = round(ms / 1000)
    return f"{total // 60}:{total % 60:02d}"


def write_skeleton(
    content_dir: Path, slug: str, info: AlbumInfo, research_urls: list[str], *, note: str
) -> Path:
    """Write a claim-free seed folder. Refuses to overwrite an existing album."""
    folder = content_dir / slug
    if (folder / "album.yaml").exists():
        raise FileExistsError(f"{folder} already has an album.yaml; choose another slug")
    (folder / "tracks").mkdir(parents=True, exist_ok=True)

    album: dict = {
        "slug": slug,
        "title": info.title,
        "artist": {
            "name": info.artist,
            **(
                {"apple_music_id": info.artist_apple_music_id} if info.artist_apple_music_id else {}
            ),
        },
    }
    if info.release_date:
        album["release_date"] = info.release_date
    if info.apple_music_id:
        album["apple_music_id"] = info.apple_music_id
    if info.artwork_url:
        album["artwork_url"] = info.artwork_url
    header = (
        f"# {info.artist}, {info.title}. {note}\n"
        "# Skeleton only: no claims yet. Run `app.research collect/extract` to propose some.\n"
    )
    (folder / "album.yaml").write_text(
        header + yaml.safe_dump(album, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    (folder / "sources.yaml").write_text("sources: []\n", encoding="utf-8")

    for t in info.tracks:
        track: dict = {"number": t.number, "title": t.title}
        if dur := _mmss(t.duration_ms):
            track["duration"] = dur
        if t.apple_music_id:
            track["apple_music_id"] = t.apple_music_id
        name = f"{t.number:02d}-{slugify(t.title)[:50] or 'track'}.yaml"
        (folder / "tracks" / name).write_text(
            yaml.safe_dump(track, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )

    if research_urls:
        (folder / "research.yaml").write_text(
            "# Pages the finder reads. Chosen automatically from the album's Wikipedia reference\n"
            "# list; edit freely (remove weak pages, add interviews you know of).\n"
            + yaml.safe_dump({"urls": research_urls}, sort_keys=False),
            encoding="utf-8",
        )
    return folder
