"""Delt testcontainers-ES-fixture for integrationstests.

Én container per test-session (opstart ~10-20 s); test-isolation opnås
via unikt index-prefix per test i stedet for container per test.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator

import pytest
from elasticsearch import AsyncElasticsearch
from testcontainers.core.wait_strategies import HttpWaitStrategy
from testcontainers.elasticsearch import ElasticSearchContainer

ES_IMAGE = "docker.elastic.co/elasticsearch/elasticsearch:8.11.4"

# P2-38. Eksplicit i stedet for arvet: testcontainers 4.14.2 sætter selv
# `_startup_timeout = testcontainers_config.timeout` = `TC_MAX_TRIES` (120) x
# `TC_POOLING_INTERVAL` (1) = 120 s, så tallet herunder ÆNDRER intet i dag. Det er
# en pin, ikke et fix: uden den afhænger grænsen af en pakke-default og af to
# env-vars, som enhver CI-runner kan sætte uden at røre denne fil.
#
# Målt baseline: pull + boot tog 36 s i den grønne kørsel (30372244517), så 120 s
# er ~3x og bliver ikke det der rammer først på en langsom, men fungerende ES.
ES_STARTUP_TIMEOUT_S = 120


@pytest.fixture(scope="session")
def es_container() -> Iterator[ElasticSearchContainer]:
    # xpack.security disables selv af ElasticSearchContainer for 8.x.
    container = ElasticSearchContainer(ES_IMAGE, mem_limit="1g")
    container.with_env("ES_JAVA_OPTS", "-Xms256m -Xmx256m")
    # Samme strategi ElasticSearchContainer selv vælger (HttpWaitStrategy på .port),
    # kun med grænsen skrevet ud.
    container.waiting_for(HttpWaitStrategy(container.port).with_startup_timeout(ES_STARTUP_TIMEOUT_S))
    #
    # HVAD DENNE GRÆNSE IKKE DÆKKER — og hvorfor P2-38's ydre grænse er den der tæller:
    #
    # `with container:` -> DockerContainer.start() gør `docker_client.run(...)`, som
    # **puller imaget**, FØR wait-strategien nogensinde kaldes. Pull'et er ubundet, og
    # testcontainers 4.14.2 eksponerer ingen knap for det. Samme gælder Ryuk-containeren.
    #
    # Det er ikke teoretisk: hængen i finding 2026-07-28 sad **836 s**. Var den i waiten,
    # var den fejlet efter 120 s. At den ikke gjorde, beviser at den lå i pull-stien —
    # altså udenfor alt hvad denne fixture kan bounde. Den reelle grænse for den klasse er
    # `timeout-minutes: 8` på `python-services` i ci.yml.
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
