"""CLI: `uv run python -m app.seed import <slug>` (run `alembic upgrade head` first)."""

import argparse
import sys

from app.config import settings
from app.db import SessionLocal
from app.services.importer import import_album
from app.services.seed_loader import SeedValidationError, load_album


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.seed")
    sub = parser.add_subparsers(dest="command", required=True)
    imp = sub.add_parser("import", help="validate and import an album's seed files")
    imp.add_argument("slug")
    args = parser.parse_args(argv)

    try:
        bundle = load_album(settings.content_dir, args.slug)
    except SeedValidationError as exc:
        print(f"{len(exc.errors)} error(s) in seed files, nothing imported:", file=sys.stderr)
        for err in exc.errors:
            print(f"  {err}", file=sys.stderr)
        return 1

    with SessionLocal() as session, session.begin():
        report = import_album(session, bundle)
    print(report.summary())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
