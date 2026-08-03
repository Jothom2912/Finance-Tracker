"""Validate or apply a hash-approved TAX-10 budget manifest."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from contracts.reclassification import authorize_execution, load_execution_manifest

from app.adapters.outbound.category_port import CategoryPort
from app.application.reclassification import apply_reclassification
from app.database import async_session_factory


async def _run(args: argparse.Namespace) -> None:
    manifest_path = Path(args.manifest).resolve()
    if args.execute:
        if not all((args.approval, args.manifest_sha256, args.approval_sha256, args.summary_sha256)):
            raise ValueError("--execute requires approval and exact summary/manifest/approval hashes")
        manifest = authorize_execution(
            manifest_path=manifest_path,
            approval_path=Path(args.approval).resolve(),
            expected_manifest_sha256=args.manifest_sha256,
            expected_approval_sha256=args.approval_sha256,
            expected_summary_sha256=args.summary_sha256,
            expected_service="budget-service",
        )
    else:
        manifest = load_execution_manifest(manifest_path, expected_service="budget-service")
    async with async_session_factory() as session, session.begin():
        result = await apply_reclassification(session, manifest, CategoryPort(), execute=args.execute)
    print(json.dumps(result, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate/apply TAX-10 budget references")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--approval")
    parser.add_argument("--manifest-sha256")
    parser.add_argument("--approval-sha256")
    parser.add_argument("--summary-sha256")
    asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    main()
