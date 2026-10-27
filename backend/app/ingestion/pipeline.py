"""Fetch -> clean -> write the snapshot (CSV + manifest) atomically."""

import hashlib
import json
import logging
import os
import time
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx
import pandas as pd

from app.ingestion.elexon import fetch_actuals, fetch_forecasts
from app.ingestion.transform import clean_forecasts, hourly_actuals
from app.repository import ACTUALS_FILE, FORECASTS_FILE, MANIFEST_FILE

log = logging.getLogger(__name__)


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def write_snapshot(
    out_dir: Path,
    forecasts: pd.DataFrame,
    actuals: pd.DataFrame,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write both CSVs and a manifest whose `version` is a content hash. Idempotent."""
    out_dir.mkdir(parents=True, exist_ok=True)
    texts = {
        FORECASTS_FILE: forecasts.to_csv(index=False, date_format="%Y-%m-%dT%H:%M:%SZ"),
        ACTUALS_FILE: actuals.to_csv(index=False, date_format="%Y-%m-%dT%H:%M:%SZ"),
    }
    version = hashlib.sha256("".join(texts[k] for k in sorted(texts)).encode()).hexdigest()[:16]
    manifest = {
        "version": version,
        "rows": {"forecasts": len(forecasts), "actuals": len(actuals)},
        "forecast_publish_range": _range(forecasts, "publish_time"),
        "target_range": _range(actuals, "start_time"),
        **(extra or {}),
    }
    for name, text in texts.items():
        _atomic_write(out_dir / name, text)
    _atomic_write(out_dir / MANIFEST_FILE, json.dumps(manifest, indent=2) + "\n")
    return manifest


def _range(df: pd.DataFrame, col: str) -> list[str] | None:
    if df.empty:
        return None
    return [df[col].min().isoformat(), df[col].max().isoformat()]


async def run(
    out_dir: Path,
    actuals_from: date,
    actuals_to: date,
    publish_from: date,
    publish_to: date,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=60) as client:
        raw_actuals = await fetch_actuals(client, actuals_from, actuals_to)
        raw_forecasts = await fetch_forecasts(client, publish_from, publish_to)
    actuals, forecasts = hourly_actuals(raw_actuals), clean_forecasts(raw_forecasts)
    manifest = write_snapshot(
        out_dir,
        forecasts,
        actuals,
        extra={
            "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "source": "https://data.elexon.co.uk/bmrs/api/v1/datasets",
        },
    )
    log.info(
        "ingest complete",
        extra={"seconds": round(time.perf_counter() - t0, 1), "rows": manifest["rows"]},
    )
    return manifest
