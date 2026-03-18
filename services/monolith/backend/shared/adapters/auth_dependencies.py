"""
FastAPI dependency factory for auth-related ports.

Isolated module to avoid circular imports between auth.py and dependencies.py.
"""

from __future__ import annotations

from backend.database.mysql import get_db
from backend.shared.adapters.mysql_account_resolver import MySQLAccountResolver
from backend.shared.ports.auth_ports import IAccountResolver
from fastapi import Depends
from sqlalchemy.orm import Session


def get_account_resolver(
    db: Session = Depends(get_db),
) -> IAccountResolver:
    """Create IAccountResolver for auth account resolution."""
    return MySQLAccountResolver(db)
