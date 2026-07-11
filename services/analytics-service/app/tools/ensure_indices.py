"""Manuel index/alias-bootstrap (samme funktion som app/consumer kalder
ved opstart)::

    python -m app.tools.ensure_indices
"""

from __future__ import annotations

import asyncio

from app.adapters.outbound.elasticsearch.bootstrap import ensure_indices
from app.adapters.outbound.elasticsearch.client import create_es_client
from app.config import settings


async def main() -> None:
    es = create_es_client(settings)
    try:
        await ensure_indices(es, settings.es_index_prefix)
    finally:
        await es.close()


if __name__ == "__main__":
    asyncio.run(main())
