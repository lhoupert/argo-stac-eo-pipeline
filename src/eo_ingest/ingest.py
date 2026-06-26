"""The frozen unit of work: resolve -> download -> register (registration gated on STAC_URL).

This module is byte-stable from rung 1 (AD-2) — the orchestration around it grows across rungs,
but ``ingest_one`` does not. It ingests a single day's item, writing assets to S3 and (when a
catalog is configured) registering the item in the logbook, then prints a ``rich`` summary line.

``FAIL_ONCE`` injects exactly one transient failure per item using an S3 marker, so the
fail-then-succeed survives an Argo retry into a fresh pod (the rung-1 retry demo).
"""

from __future__ import annotations

import argparse
import time
from datetime import date, timedelta

from botocore.exceptions import ClientError
from rich.console import Console

from .config import Config, load_config
from .download import _s3_client, _split_s3_uri, download_item
from .logbook import register
from .stac_source import resolve_items

_console = Console()
_FAIL_MARKER_PREFIX = "_fail_once"
_DEFAULT_DAY = date(2026, 3, 14)


class TransientIngestError(RuntimeError):
    """A deliberately-injected transient failure (FAIL_ONCE) — succeeds on retry."""


def _maybe_fail_once(config: Config, s3, bucket: str, item_id: str) -> None:
    """Fail once per item: the first attempt drops an S3 marker and raises; the retry sees it."""
    if not config.fail_once:
        return
    key = f"{_FAIL_MARKER_PREFIX}/{item_id}"
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return  # marker present => this is the retry, proceed
    except ClientError as exc:
        if exc.response["Error"]["Code"] not in ("404", "NoSuchKey", "NotFound"):
            raise
    s3.put_object(Bucket=bucket, Key=key, Body=b"1")
    raise TransientIngestError(f"FAIL_ONCE: injected one transient failure for {item_id}")


def _asset_bytes(s3, bucket: str, item: dict) -> int:
    total = 0
    for asset in item["assets"].values():
        _, key = _split_s3_uri(asset["href"])
        total += s3.head_object(Bucket=bucket, Key=key)["ContentLength"]
    return total


def _print_summary(
    config: Config, item: dict, total_bytes: int, register_action: str | None
) -> None:
    registered = register_action if config.registration_enabled else "disabled"
    _console.print(
        f"[green]✓[/] ingested [bold]{item['id']}[/]  {item['collection']}  "
        f"bbox={item['bbox']}  {total_bytes:,} B  registered={registered}"
    )


def ingest_one(config: Config, day: date) -> dict:
    """Ingest the single item for ``day``: assets to S3, then register if a catalog is set."""
    items = resolve_items(config, day, day + timedelta(days=1))
    if not items:
        _console.print(f"[yellow]nothing to ingest for {day.isoformat()}[/]")
        return {"ingested": 0}
    item = items[0]

    s3 = _s3_client(config)
    _maybe_fail_once(config, s3, config.s3_bucket, item["id"])

    if config.ingest_sleep:
        time.sleep(config.ingest_sleep)

    actions = download_item(config, item)
    total_bytes = _asset_bytes(s3, config.s3_bucket, item)

    register_action = register(config, item) if config.registration_enabled else None
    _print_summary(config, item, total_bytes, register_action)

    return {
        "ingested": 1,
        "item_id": item["id"],
        "bytes": total_bytes,
        "actions": actions,
        "registered": config.registration_enabled,
        "register_action": register_action,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="eo_ingest.ingest", description="Ingest one EO item.")
    parser.add_argument(
        "--day", type=date.fromisoformat, default=_DEFAULT_DAY, help="observation day (YYYY-MM-DD)"
    )
    args = parser.parse_args(argv)
    ingest_one(load_config(), args.day)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
