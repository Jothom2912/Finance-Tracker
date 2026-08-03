"""Validate or apply a hash-approved TAX-10 transaction manifest."""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import hmac
import json
from pathlib import Path
from time import time

import httpx
from contracts.reclassification import authorize_execution, load_execution_manifest

from app.application.reclassification import ResolvedTaxonomyTarget, apply_reclassification
from app.config import settings
from app.database import async_session_factory


def _service_auth_header() -> dict[str, str]:
    def encode(value: object) -> str:
        payload = json.dumps(value, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(payload).rstrip(b"=").decode()

    header = encode({"alg": settings.JWT_ALGORITHM, "typ": "JWT"})
    claims = encode({"sub": "0", "user_id": 0, "exp": int(time()) + 300})
    signing_input = f"{header}.{claims}".encode()
    signature = base64.urlsafe_b64encode(
        hmac.new(settings.JWT_SECRET.encode(), signing_input, hashlib.sha256).digest()
    ).rstrip(b"=")
    return {"Authorization": f"Bearer {header}.{claims}.{signature.decode()}"}


class _TaxonomyResolver:
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url
        self._targets: dict[tuple[str, str], ResolvedTaxonomyTarget] | None = None

    async def resolve(self, semantic_key: str, public_id: str) -> ResolvedTaxonomyTarget | None:
        if self._targets is None:
            headers = _service_auth_header()
            async with httpx.AsyncClient(base_url=self._base_url, timeout=10.0) as client:
                categories_response = await client.get("/api/v1/categories/", headers=headers)
                subcategories_response = await client.get("/api/v1/subcategories/", headers=headers)
                categories_response.raise_for_status()
                subcategories_response.raise_for_status()
            categories = {int(item["id"]): item for item in categories_response.json()}
            targets: dict[tuple[str, str], ResolvedTaxonomyTarget] = {}
            for item in subcategories_response.json():
                parent = categories[int(item["category_id"])]
                if item.get("lifecycle") != "active" or parent.get("lifecycle") != "active":
                    continue
                target = ResolvedTaxonomyTarget(
                    subcategory_id=int(item["id"]),
                    subcategory_name=str(item["name"]),
                    subcategory_key=str(item["semantic_key"]),
                    subcategory_public_id=str(item["public_id"]),
                    category_id=int(parent["id"]),
                    category_name=str(parent["name"]),
                    category_type=str(parent["type"]),
                    category_key=str(parent["semantic_key"]),
                    category_public_id=str(parent["public_id"]),
                )
                targets[(target.subcategory_key, target.subcategory_public_id)] = target
            self._targets = targets
        return self._targets.get((semantic_key, public_id))


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
            expected_service="transaction-service",
        )
    else:
        manifest = load_execution_manifest(manifest_path, expected_service="transaction-service")
    async with async_session_factory() as session, session.begin():
        resolver = _TaxonomyResolver(args.taxonomy_url) if args.taxonomy_url else None
        result = await apply_reclassification(
            session,
            manifest,
            execute=args.execute,
            taxonomy_resolver=resolver,
        )
    print(json.dumps(result, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate/apply TAX-10 transaction references")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--approval")
    parser.add_argument("--manifest-sha256")
    parser.add_argument("--approval-sha256")
    parser.add_argument("--summary-sha256")
    parser.add_argument("--taxonomy-url", help="Categorization API used to repair missing local TAX-06 identities")
    asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    main()
