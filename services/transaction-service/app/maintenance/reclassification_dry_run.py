"""Operator entry point for the transaction-service TAX-07 shard."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from contracts.reclassification import load_mapping, write_report
from sqlalchemy import text

from app.adapters.outbound.categorization_client import CategorizationClient
from app.application.reclassification import scan_transactions
from app.database import async_session_factory


async def _run(args: argparse.Namespace) -> None:
    mapping = load_mapping(Path(args.mapping))
    async with async_session_factory() as session, session.begin():
        if session.bind is not None and session.bind.dialect.name == "postgresql":
            await session.execute(text("SET TRANSACTION READ ONLY"))
        report = await scan_transactions(
            session,
            run_id=args.run_id,
            captured_at=args.captured_at,
            mapping=mapping,
            evidence_categorizer=CategorizationClient(),
        )
    write_report(report, Path(args.output_dir).resolve())


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the read-only TAX-07 transaction shard")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--captured-at", required=True)
    parser.add_argument("--mapping", required=True)
    parser.add_argument("--output-dir", required=True)
    asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    main()
