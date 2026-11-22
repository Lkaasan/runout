"""On-disk cache for the information finder.

Two stores under one root (default `.research-cache/`, gitignored, never served):
- `http/`: every response we fetched, keyed by full URL. A second run reads from here and makes
  no network calls.
- `pages/<slug>/`: the assembled pages for an album, which later stages read.
"""

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.pipeline.models import Page


@dataclass(frozen=True)
class HttpRecord:
    url: str
    status: int
    fetched_at: datetime
    text: str


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "page"


class ResearchCache:
    def __init__(self, root: Path):
        self.root = Path(root)

    # ---- raw responses -------------------------------------------------------------------

    def _http_path(self, url: str) -> Path:
        return self.root / "http" / (hashlib.sha256(url.encode()).hexdigest() + ".json")

    def get(self, url: str) -> HttpRecord | None:
        path = self._http_path(url)
        if not path.exists():
            return None
        data = json.loads(path.read_text("utf-8"))
        return HttpRecord(
            url=data["url"],
            status=data["status"],
            fetched_at=datetime.fromisoformat(data["fetched_at"]),
            text=data["text"],
        )

    def put(self, url: str, status: int, text: str) -> HttpRecord:
        record = HttpRecord(url=url, status=status, fetched_at=datetime.now(UTC), text=text)
        path = self._http_path(url)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "url": record.url,
                    "status": record.status,
                    "fetched_at": record.fetched_at.isoformat(),
                    "text": record.text,
                }
            ),
            encoding="utf-8",
        )
        return record

    # ---- assembled pages -----------------------------------------------------------------

    def _pages_dir(self, slug: str) -> Path:
        return self.root / "pages" / slug

    def put_pages(self, slug: str, pages: list[Page]) -> None:
        folder = self._pages_dir(slug)
        folder.mkdir(parents=True, exist_ok=True)
        for old in folder.glob("*.json"):
            old.unlink()
        for i, page in enumerate(pages, start=1):
            name = f"{i:02d}-{page.kind}-{_slugify(page.title)}.json"
            (folder / name).write_text(page.model_dump_json(indent=1), encoding="utf-8")

    def get_pages(self, slug: str) -> list[Page]:
        folder = self._pages_dir(slug)
        return [
            Page.model_validate_json(p.read_text("utf-8")) for p in sorted(folder.glob("*.json"))
        ]
