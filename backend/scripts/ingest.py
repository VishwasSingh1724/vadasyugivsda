"""Refresh the data snapshot from Elexon.  Usage: python -m scripts.ingest [--out DIR]"""

import argparse
import asyncio
from datetime import date
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.ingestion.pipeline import run


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=get_settings().data_dir)
    # Decisions in Jan 2026 -> delivery days 2 Jan..1 Feb; forecasts published 31 Dec..31 Jan.
    p.add_argument("--actuals-from", type=date.fromisoformat, default=date(2026, 1, 2))
    p.add_argument("--actuals-to", type=date.fromisoformat, default=date(2026, 2, 1))
    p.add_argument("--publish-from", type=date.fromisoformat, default=date(2025, 12, 31))
    p.add_argument("--publish-to", type=date.fromisoformat, default=date(2026, 1, 31))
    a = p.parse_args()
    configure_logging("INFO")
    manifest = asyncio.run(run(a.out, a.actuals_from, a.actuals_to, a.publish_from, a.publish_to))
    print(manifest)


if __name__ == "__main__":
    main()
