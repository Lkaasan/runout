"""CLI for the information finder: `uv run python -m app.research score <slug> --oracle`.

Step 0 only has `score`. Collecting, extracting and verifying arrive in later steps.
"""

import argparse
import sys
from pathlib import Path

from app.config import settings
from app.pipeline.models import Proposal
from app.pipeline.scoring import load_gold, proposal_from_seed, score
from app.services.seed_loader import load_album


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.research")
    sub = parser.add_subparsers(dest="command", required=True)

    sc = sub.add_parser("score", help="score a proposal against the gold set")
    sc.add_argument("slug")
    which = sc.add_mutually_exclusive_group(required=True)
    which.add_argument("--empty", action="store_true", help="a run that found nothing (floor)")
    which.add_argument("--oracle", action="store_true", help="the reviewed seed as a run (ceiling)")
    which.add_argument("--proposal", type=Path, help="a proposal JSON file")
    args = parser.parse_args(argv)

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
