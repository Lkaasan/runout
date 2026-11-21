"""Writes the OpenAPI schema: `uv run python -m app.export_openapi ../web/openapi.json`."""

import json
import sys
from pathlib import Path

from app.main import app


def main() -> None:
    text = json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"
    # LF on every OS so the committed file is identical to what CI regenerates.
    with Path(sys.argv[1]).open("w", encoding="utf-8", newline="\n") as f:
        f.write(text)


if __name__ == "__main__":
    main()
