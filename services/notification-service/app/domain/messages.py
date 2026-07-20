"""Danish message builders — pure functions from event data to
:class:`NotificationContent`.

Kept free of I/O and clock reads so every branch (zero imports, errors,
singular/plural, surplus formatting, month names) is unit-testable. Text
is Danish to match the rest of the product surface.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from app.domain.entities import NotificationContent, NotificationType

# 1-indexed; index 0 unused so month numbers map directly.
_MONTHS_DA = (
    "",
    "januar",
    "februar",
    "marts",
    "april",
    "maj",
    "juni",
    "juli",
    "august",
    "september",
    "oktober",
    "november",
    "december",
)


def format_amount(amount: Decimal) -> str:
    """Format a money amount in Danish style: ``1.234,56`` (grouping ``.``,
    decimal ``,``). Negative amounts keep a leading minus."""
    q = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    negative = q < 0
    # '1,234.56' (en) -> '1.234,56' (da) via a swap through a placeholder.
    grouped = f"{abs(q):,.2f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return f"-{grouped}" if negative else grouped


def _month_name(month: int) -> str:
    if 1 <= month <= 12:
        return _MONTHS_DA[month]
    return str(month)


def _transaction_word(count: int) -> str:
    return "transaktion" if count == 1 else "transaktioner"


def build_bank_sync_completed(*, new_imported: int, errors: int) -> NotificationContent:
    if new_imported == 0:
        body = "Din bank er synkroniseret – ingen nye transaktioner."
    else:
        body = f"{new_imported} {_transaction_word(new_imported)} blev importeret."
    if errors > 0:
        body += f" {errors} {_transaction_word(errors)} kunne ikke behandles."
    return NotificationContent(
        type=NotificationType.BANK_SYNC_COMPLETED,
        title="Banksynkronisering færdig",
        body=body,
    )


def build_goal_reached(*, goal_name: str | None, target_amount: Decimal) -> NotificationContent:
    amount = format_amount(target_amount)
    if goal_name:
        body = f"Du har nået dit mål “{goal_name}” på {amount} kr. Flot klaret!"
    else:
        body = f"Du har nået dit sparemål på {amount} kr. Flot klaret!"
    return NotificationContent(
        type=NotificationType.GOAL_REACHED,
        title="Mål nået! 🎉",
        body=body,
    )


def build_budget_month_closed(*, year: int, month: int, surplus_amount: Decimal) -> NotificationContent:
    period = f"{_month_name(month)} {year}"
    if surplus_amount > 0:
        body = f"{period} er gjort op med et overskud på {format_amount(surplus_amount)} kr."
    else:
        body = f"{period} er gjort op. Der var intet overskud denne måned."
    return NotificationContent(
        type=NotificationType.BUDGET_MONTH_CLOSED,
        title="Måned lukket",
        body=body,
    )
