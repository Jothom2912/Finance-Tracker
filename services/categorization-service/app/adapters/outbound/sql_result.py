"""Small SQLAlchemy typing helpers shared by this service's repositories."""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy import CursorResult, Result


def rowcount(result: Result[Any]) -> int:
    """Rows touched by a DML statement.

    ``AsyncSession.execute`` is annotated as returning ``Result``, which has no
    ``rowcount`` — but for UPDATE/DELETE it always hands back a ``CursorResult``,
    which does. The narrowing is a stub limitation, not a runtime uncertainty, so
    it lives here once instead of at each call site.
    """
    return cast("CursorResult[Any]", result).rowcount
