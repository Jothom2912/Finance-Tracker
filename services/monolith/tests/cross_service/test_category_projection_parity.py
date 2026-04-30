"""Live parity test — MySQL Category projection vs Postgres categories.

This is the operational-state check that complements the fast static
drift test in ``tests/architecture/test_category_seed_parity.py``.
The static test catches "somebody edited one seed file but not the
other".  This test catches "the projection has drifted from its
source at runtime" — which is exactly the bug that hid behind
"Ukendt" in the UI for hours during the 2026-04-17 sync incident.

Tests skip automatically when the docker-compose stack isn't up
(see conftest.py), so the fast-feedback ``make test`` workflow is
unaffected.  Run via ``make test-cross-service`` to exercise them
against a live environment.

Assertions are narrow on purpose: only ``{id, name}`` is compared,
because:

* ``type`` is checked at an event level by the architecture test
  (``test_default_taxonomy_types_are_supported_by_transaction_service``).
* ``display_order`` is a monolith-only UI concern that intentionally
  doesn't cross the service boundary.

If a new attribute is ever added to the cross-service contract,
extend the query — don't remove these existing assertions.
"""

from __future__ import annotations


def _fetch_postgres_categories(postgres_conn) -> dict[int, str]:  # type: ignore[no-untyped-def]
    with postgres_conn.cursor() as cur:
        cur.execute("SELECT id, name FROM categories")
        return {row[0]: row[1] for row in cur.fetchall()}


def _fetch_mysql_categories(mysql_conn) -> dict[int, str]:  # type: ignore[no-untyped-def]
    with mysql_conn.cursor() as cur:
        cur.execute("SELECT idCategory, name FROM Category")
        return {row[0]: row[1] for row in cur.fetchall()}


def test_category_id_sets_match(postgres_conn, mysql_conn) -> None:  # type: ignore[no-untyped-def]
    """Every category that exists in one database must exist in the
    other with the same id.

    If this fails: the projection has drifted.  Most common causes:

    * ``CategorySyncConsumer`` is not running, or RabbitMQ is down,
      so new categories created in Postgres never reach MySQL.
    * Someone inserted directly into MySQL ``Category`` bypassing the
      event stream (the fitness test
      ``test_no_writes_to_read_only_projections`` is supposed to
      prevent this, but it only catches AST-level patterns).
    * A Postgres volume was recreated without replaying migration
      006's seed events.
    """
    pg = _fetch_postgres_categories(postgres_conn)
    mysql = _fetch_mysql_categories(mysql_conn)

    only_pg = set(pg) - set(mysql)
    only_mysql = set(mysql) - set(pg)

    assert not only_pg and not only_mysql, (
        f"Category id-sets differ between services.\n"
        f"  Ids only in Postgres (transaction-service): "
        f"{sorted(only_pg)} -> {[pg[i] for i in sorted(only_pg)]}\n"
        f"  Ids only in MySQL (monolith projection):   "
        f"{sorted(only_mysql)} -> {[mysql[i] for i in sorted(only_mysql)]}\n"
        "If Postgres has more rows, the projection pipeline (outbox-worker "
        "+ category-sync-consumer + rabbitmq) is lagging or broken.\n"
        "If MySQL has more rows, something is writing directly to the "
        "read-only Category projection."
    )


def test_category_names_match_for_same_ids(postgres_conn, mysql_conn) -> None:  # type: ignore[no-untyped-def]
    """For every shared id, the ``name`` must agree.

    Name drift is more insidious than id drift: the UI still renders
    *a* category so nothing looks broken, but the label is stale.
    """
    pg = _fetch_postgres_categories(postgres_conn)
    mysql = _fetch_mysql_categories(mysql_conn)

    mismatches = [(id_, mysql[id_], pg[id_]) for id_ in set(pg) & set(mysql) if mysql[id_] != pg[id_]]

    assert not mismatches, (
        "Categories with matching ids have different names:\n"
        + "\n".join(f"  id={id_}  mysql={m!r}  postgres={p!r}" for id_, m, p in mismatches)
        + "\nThe projection is stale — check that category-sync-consumer "
        "processed the corresponding category.updated events."
    )


def test_no_orphaned_transaction_category_ids(postgres_conn) -> None:  # type: ignore[no-untyped-def]
    """No transaction in Postgres may reference a ``category_id`` that
    doesn't exist in the ``categories`` table.

    This is item (2) of the drift audit, applied to live data rather
    than a Testcontainers fixture.  An orphan here means a producer
    (bank sync, CSV import, manual entry) wrote an id that was never
    a valid category — or the category has since been deleted without
    the transactions being reassigned.
    """
    with postgres_conn.cursor() as cur:
        cur.execute(
            "SELECT t.category_id, COUNT(*) "
            "FROM transactions t "
            "LEFT JOIN categories c ON c.id = t.category_id "
            "WHERE t.category_id IS NOT NULL AND c.id IS NULL "
            "GROUP BY t.category_id "
            "ORDER BY COUNT(*) DESC"
        )
        orphan_ids = cur.fetchall()

    assert not orphan_ids, (
        "Transactions reference category ids that don't exist in the "
        "categories table:\n"
        + "\n".join(f"  category_id={cid}  orphan_count={n}" for cid, n in orphan_ids)
        + "\nInvestigate the producer that wrote these — most likely "
        "a rule engine built its lookup from a different database "
        "state than the one transactions land in."
    )
