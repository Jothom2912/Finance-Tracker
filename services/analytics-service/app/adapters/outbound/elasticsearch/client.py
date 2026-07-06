from __future__ import annotations

from elasticsearch import AsyncElasticsearch

from app.config import Settings


def create_es_client(settings: Settings) -> AsyncElasticsearch:
    return AsyncElasticsearch(settings.elasticsearch_url)
