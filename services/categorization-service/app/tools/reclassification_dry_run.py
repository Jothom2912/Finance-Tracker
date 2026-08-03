"""Operator entry point for the categorization-service TAX-07 shard."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from contracts.reclassification import write_report
from sqlalchemy import text

from app.application.reclassification import scan_categorization
from app.database import async_session_factory
from app.domain.reclassification import mapping_bytes


async def _run(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir).resolve()
    async with async_session_factory() as session, session.begin():
        if session.bind is not None and session.bind.dialect.name == "postgresql":
            await session.execute(text("SET TRANSACTION READ ONLY"))
        report = await scan_categorization(session, run_id=args.run_id, captured_at=args.captured_at)
    write_report(report, output_dir)
    (output_dir / "taxonomy-mapping.json").write_bytes(mapping_bytes())


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the read-only TAX-07 categorization shard")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--captured-at", required=True, help="Pinned UTC snapshot boundary")
    parser.add_argument("--output-dir", required=True)
    asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    main()
