"""CLI for the information finder: `uv run python -m app.research score <slug> --oracle`.

`collect` (step 1) fetches source pages with no AI; `score` (step 0) grades a run. Extracting
and verifying arrive in later steps.
"""

import argparse
import sys
from pathlib import Path

from app.config import settings
from app.pipeline.cache import ResearchCache
from app.pipeline.collect import collect_album
from app.pipeline.http import Fetcher
from app.pipeline.models import Proposal
from app.pipeline.scoring import load_gold, proposal_from_seed, score
from app.services.seed_loader import load_album


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.research")
    sub = parser.add_subparsers(dest="command", required=True)

    co = sub.add_parser("collect", help="fetch MusicBrainz and Wikipedia pages (no AI)")
    co.add_argument("slug")
    co.add_argument("--refresh", action="store_true", help="ignore the cache and fetch again")

    sc = sub.add_parser("score", help="score a proposal against the gold set")
    sc.add_argument("slug")
    which = sc.add_mutually_exclusive_group(required=True)
    which.add_argument("--empty", action="store_true", help="a run that found nothing (floor)")
    which.add_argument("--oracle", action="store_true", help="the reviewed seed as a run (ceiling)")
    which.add_argument("--proposal", type=Path, help="a proposal JSON file")
    args = parser.parse_args(argv)

    if args.command == "collect":
        cache = ResearchCache(settings.research_cache_dir)
        fetcher = Fetcher(cache, refresh=args.refresh)
        report = collect_album(load_album(settings.content_dir, args.slug), fetcher, cache)
        print(report.summary())
        return 0 if report.pages else 1

    gold = load_gold(args.slug)
    if args.empty:
        proposal = Proposal(slug=args.slug)
    elif args.oracle:
        proposal = proposal_from_seed(load_album(settings.content_dir, args.slug))
    else:
        proposal = Proposal.model_validate_json(args.proposal.read_text("utf-8"))

    result = score(gold, proposal)
    print(result.report())
    return 0 if result.errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
