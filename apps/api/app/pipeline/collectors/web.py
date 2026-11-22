"""Ordinary web pages the album's owner points us at (articles, interviews, press).

The list lives in `content/albums/<slug>/research.yaml`, so what the finder reads is chosen by a
person and reviewable in git. Pages are fetched politely (robots.txt respected, cached) and
reduced to their article text. Step 4 will find such pages by searching; this step only reads the
ones it is given.
"""

import re
from pathlib import Path
from urllib.parse import urlparse

import yaml
from bs4 import BeautifulSoup

from app.pipeline.http import Fetcher, FetchError
from app.pipeline.models import Page

# Parts of a page that are never the article.
_NOISE = (
    "script",
    "style",
    "noscript",
    "nav",
    "footer",
    "header",
    "aside",
    "form",
    "iframe",
    "svg",
)


def load_research_urls(content_dir: Path, slug: str) -> list[str]:
    """URLs listed in content/albums/<slug>/research.yaml (`urls:`); none if the file is absent."""
    path = content_dir / slug / "research.yaml"
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text("utf-8")) or {}
    urls = data.get("urls", [])
    bad = [u for u in urls if not (isinstance(u, str) and urlparse(u).scheme in ("http", "https"))]
    if bad:
        raise ValueError(f"{path}: not http(s) URLs: {bad}")
    return urls


_BLOCKS = ("p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "figcaption", "dd", "dt")


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def html_to_text(html: str) -> tuple[str, str]:
    """(title, article text), one line per paragraph.

    Inline markup (links, italics) is joined exactly as written, so "<em>Animals</em>, the album"
    reads "Animals, the album" and not "Animals , the album". A quote copied from the page then
    still matches it word for word.
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(_NOISE):
        tag.decompose()
    title = (soup.title.get_text(strip=True) if soup.title else "") or ""
    heading = soup.find("h1")
    if heading and heading.get_text(strip=True):
        title = _squash(heading.get_text(""))
    root = soup.find("article") or soup.find("main") or soup.body or soup

    paragraphs = []
    for el in root.find_all(_BLOCKS):
        if el.find(_BLOCKS):  # a container: its own paragraphs are visited separately
            continue
        text = _squash(el.get_text(""))
        if text:
            paragraphs.append(text)
    text = "\n".join(paragraphs)
    if len(text) < 200:  # unusual markup without paragraphs: fall back to all text
        lines = [_squash(line) for line in root.get_text("\n").splitlines()]
        text = "\n".join(line for line in lines if line)
    return title, text


class WebCollector:
    def __init__(self, fetcher: Fetcher):
        self.fetcher = fetcher

    def collect(self, urls: list[str]) -> tuple[list[Page], list[str]]:
        pages: list[Page] = []
        notes: list[str] = []
        for url in urls:
            try:
                record = self.fetcher.fetch(url)
            except FetchError as exc:
                notes.append(f"Could not read {url}: {exc}")
                continue
            if record.text.lstrip().startswith("%PDF"):
                notes.append(f"{url}: a PDF, which the finder cannot read yet")
                continue
            title, text = html_to_text(record.text)
            if len(text) < 200:
                notes.append(f"{url}: no readable article text found")
                continue
            pages.append(
                Page(
                    url=url,
                    title=title or url,
                    kind="web",
                    fetched_at=record.fetched_at,
                    text=text,
                    meta={"domain": (urlparse(url).hostname or "").removeprefix("www.")},
                )
            )
        return pages, notes
