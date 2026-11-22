"""CLI for the information finder: `uv run python -m app.research score <slug> --oracle`.

`collect` (step 1) fetches source pages with no AI; `extract` (step 2) asks Claude Code to
propose claims and runs the deterministic checks; `score` (step 0) grades a run. The verifier
arrives in step 3.
"""

import argparse
import sys
from pathlib import Path

from app.config import settings
from app.pipeline.cache import ResearchCache
from app.pipeline.collect import collect_album
from app.pipeline.http import Fetcher
from app.pipeline.llm import ClaudeCodeBackend, LLMError
from app.pipeline.models import Proposal
from app.pipeline.render import write_run
from app.pipeline.run import run_extraction
from app.pipeline.scoring import load_gold, proposal_from_seed, score
from app.services.seed_loader import load_album


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.research")
    sub = parser.add_subparsers(dest="command", required=True)

    co = sub.add_parser("collect", help="fetch MusicBrainz and Wikipedia pages (no AI)")
    co.add_argument("slug")
    co.add_argument("--refresh", action="store_true", help="ignore the cache and fetch again")

    ex = sub.add_parser("extract", help="propose claims from collected pages (uses Claude Code)")
    ex.add_argument("slug")
    ex.add_argument("--model", default=settings.research_model)
    ex.add_argument("--effort", default=settings.research_effort)
    ex.add_argument(
        "--ignore-seed",
        action="store_true",
        help="do not drop proposals the seed already says (for measuring against the gold set)",
    )

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

    if args.command == "extract":
        return _extract(args)

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


def _extract(args) -> int:
    bundle = load_album(settings.content_dir, args.slug)
    pages = ResearchCache(settings.research_cache_dir).get_pages(args.slug)
    if not pages:
        print(
            f"No collected pages for '{args.slug}'. Run: python -m app.research collect {args.slug}"
        )
        return 1
    backend = ClaudeCodeBackend(model=args.model, effort=args.effort)
    try:
        result = run_extraction(bundle, pages, backend, skip_existing=not args.ignore_seed)
    except LLMError as exc:
        print(f"Extraction stopped: {exc}", file=sys.stderr)
        return 1
    folder = write_run(result, settings.content_dir)
    print(result.summary())
    u = backend.usage
    print(
        f"{u.calls} model call(s), {u.seconds:.0f}s, about ${u.cost_usd:.2f} at list price "
        "(counted against your Claude subscription, not billed)."
    )
    print(f"Wrote {folder}")
    try:
        print(score(load_gold(args.slug), result.proposal).report())
    except FileNotFoundError:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
