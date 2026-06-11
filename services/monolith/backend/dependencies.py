# backend/dependencies.py
"""
FastAPI dependency injection wiring.

This module creates service instances with constructor-injected
dependencies for FastAPI's Depends().

All active domains use hexagonal architecture, including analytics.

Usage in routes:
    from backend.dependencies import get_analytics_service

    @router.get("/")
    def overview(service: AnalyticsService = Depends(get_analytics_service)):
        return service.get_financial_overview(...)
"""

import logging

from fastapi import Depends
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Account domain removed — account-service owns this now (Phase 4 cutover)
from backend.analytics.adapters.outbound.elasticsearch_repository import (
    ElasticsearchAnalyticsReadRepository,
)
from backend.analytics.adapters.outbound.mysql_repository import (
    MySQLAnalyticsReadRepository,
)
from backend.analytics.adapters.outbound.neo4j_repository import (
    Neo4jAnalyticsReadRepository,
)

# Hexagonal Analytics domain
from backend.analytics.application.service import AnalyticsService
from backend.category.adapters.outbound.mysql_repository import (
    MySQLCategoryRepository as HexMySQLCategoryRepository,
)
from backend.category.adapters.outbound.mysql_subcategory_repository import (
    MySQLSubCategoryRepository,
)
from backend.category.adapters.outbound.rule_engine import RuleEngine
from backend.category.application.categorization_service import (
    CategorizationService,
)

# Hexagonal Category domain
from backend.category.application.service import CategoryService
from backend.category.domain.taxonomy import SEED_MERCHANT_MAPPINGS
from backend.config import ANALYTICS_DB, DatabaseType
from backend.database.mysql import get_db
from backend.goal.adapters.outbound.account_adapter import (
    MySQLAccountAdapter as GoalAccountAdapter,
)
from backend.goal.adapters.outbound.mysql_goal_repository import (
    MySQLGoalRepository as HexMySQLGoalRepository,
)

# Hexagonal Goal domain
from backend.goal.application.service import GoalService as HexGoalService
from backend.user.adapters.outbound.account_adapter import (
    MySQLAccountAdapter as UserAccountAdapter,
)
from backend.user.adapters.outbound.mysql_user_repository import (
    MySQLUserRepository as HexMySQLUserRepository,
)

# Hexagonal User domain
from backend.user.application.service import UserService as HexUserService


def get_categorization_service(
    db: Session = Depends(get_db),
) -> CategorizationService | None:
    """Create CategorizationService with rule engine (tier 1 only for now).

    Returns None when subcategories haven't been seeded yet (e.g. test
    environments). TransactionService handles None gracefully by falling
    back to the legacy keyword-based categorizer.
    """
    try:
        sub_repo = MySQLSubCategoryRepository(db)
        all_subs = sub_repo.get_all()
    except Exception:
        logger.warning("SubCategory table not available — categorization service disabled.")
        return None

    cat_repo = HexMySQLCategoryRepository(db)
    all_cats = cat_repo.get_all()
    cat_id_lookup = {cat.id: cat.id for cat in all_cats}

    subcategory_lookup: dict[str, tuple[int, int]] = {}
    for sub in all_subs:
        if sub.category_id in cat_id_lookup:
            subcategory_lookup[sub.name] = (sub.id, sub.category_id)

    keyword_mappings = [(kw, mapping["subcategory"]) for kw, mapping in SEED_MERCHANT_MAPPINGS.items()]

    rule_engine = RuleEngine(
        keyword_mappings=keyword_mappings,
        subcategory_lookup=subcategory_lookup,
    )

    fallback_ids = subcategory_lookup.get("Anden")
    if fallback_ids is None:
        logger.warning(
            "Fallback subcategory 'Anden' not found — categorization service disabled. "
            "Run seed_categories.py to enable."
        )
        return None

    return CategorizationService(
        rule_engine=rule_engine,
        fallback_subcategory_id=fallback_ids[0],
        fallback_category_id=fallback_ids[1],
    )


def get_analytics_service(
    db: Session = Depends(get_db),
) -> AnalyticsService:
    """Create AnalyticsService with DB-specific read adapter."""
    if ANALYTICS_DB == DatabaseType.ELASTICSEARCH.value:
        return AnalyticsService(read_repo=ElasticsearchAnalyticsReadRepository())
    if ANALYTICS_DB == DatabaseType.NEO4J.value:
        return AnalyticsService(read_repo=Neo4jAnalyticsReadRepository())
    return AnalyticsService(read_repo=MySQLAnalyticsReadRepository(db))


def get_category_service(
    db: Session = Depends(get_db),
) -> CategoryService:
    """Create CategoryService with hexagonal architecture repository."""
    return CategoryService(
        category_repo=HexMySQLCategoryRepository(db),
    )


def get_goal_service(
    db: Session = Depends(get_db),
) -> HexGoalService:
    """Create hexagonal GoalService with proper repositories."""
    return HexGoalService(
        goal_repository=HexMySQLGoalRepository(db),
        account_port=GoalAccountAdapter(db),
    )


def get_user_service(
    db: Session = Depends(get_db),
) -> HexUserService:
    """Create hexagonal UserService with proper repositories."""
    return HexUserService(
        user_repository=HexMySQLUserRepository(db),
        account_port=UserAccountAdapter(db),
    )
