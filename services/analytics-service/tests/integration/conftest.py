"""Delt testcontainers-ES-fixture for integrationstests.

Én container per test-session (opstart ~10-20 s); test-isolation opnås
via unikt index-prefix per test i stedet for container per test.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator

import pytest
from elasticsearch import AsyncElasticsearch
from testcontainers.elasticsearch import ElasticSearchContainer

ES_IMAGE = "docker.elastic.co/elasticsearch/elasticsearch:8.11.4"


@pytest.fixture(scope="session")
def es_container() -> Iterator[ElasticSearchContainer]:
    # xpack.security disables selv af ElasticSearchContainer for 8.x.
    container = ElasticSearchContainer(ES_IMAGE, mem_limit="1g")
    container.with_env("ES_JAVA_OPTS", "-Xms256m -Xmx256m")
    with container:
        yield container


@pytest.fixture
async def es(es_container: ElasticSearchContainer) -> AsyncIterator[AsyncElasticsearch]:
    host = es_container.get_container_host_ip()
    port = es_container.get_exposed_port(es_container.port)
    client = AsyncElasticsearch(f"http://{host}:{port}")
    try:
        yield client
    finally:
        await client.close()


@pytest.fixture
def index_prefix() -> str:
    return f"test-{uuid.uuid4().hex[:8]}-"
