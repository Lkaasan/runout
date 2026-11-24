"""CLI: `uv run python -m app.seed import <slug>` or `import --all`.

Run `alembic upgrade head` first. `--all` imports every album folder under content/albums/, so a
fresh checkout shows everything we have.
"""

import argparse
import sys
from pathlib import Path

from app.config import settings
from app.db import SessionLocal
from app.services.importer import import_album
from app.services.seed_loader import SeedValidationError, load_album


def album_slugs(content_dir: Path) -> list[str]:
    """Every folder that holds an album.yaml (a skeleton with no claims counts)."""
    if not content_dir.is_dir():
        return []
    return sorted(p.name for p in content_dir.iterdir() if (p / "album.yaml").is_file())


def import_one(slug: str) -> bool:
    """Validate and import one album. Prints what happened; returns False if it was invalid."""
    try:
        bundle = load_album(settings.content_dir, slug)
    except SeedValidationError as exc:
        print(
            f"{slug}: {len(exc.errors)} error(s) in seed files, nothing imported:", file=sys.stderr
        )
        for err in exc.errors:
            print(f"  {err}", file=sys.stderr)
        return False
    with SessionLocal() as session, session.begin():
        report = import_album(session, bundle)
    print(report.summary())
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.seed")
    sub = parser.add_subparsers(dest="command", required=True)
    imp = sub.add_parser("import", help="validate and import an album's seed files")
    imp.add_argument("slug", nargs="?", help="the album's folder name")
    imp.add_argument("--all", action="store_true", help="import every album under content/albums/")
    args = parser.parse_args(argv)

    if args.all == bool(args.slug):
        parser.error("give an album slug, or --all, but not both")

    slugs = album_slugs(settings.content_dir) if args.all else [args.slug]
    if not slugs:
        print(f"No albums found in {settings.content_dir}", file=sys.stderr)
        return 1
    # Keep going after a bad album so one mistake does not hide the rest.
    results = [import_one(slug) for slug in slugs]
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
