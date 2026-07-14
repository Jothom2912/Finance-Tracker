"""Prosa-repræsentation af et transaktionsdokument til embedding (AI-20).

Samme form som ai-services ChromaDB-ingest (dansk prosa: type, beløb,
merchant, dato, kategori) så kNN-siden af hybrid search matcher det,
query-siden (ai-service) embedder — men UDEN ai-services kategorisynonym-
map: kategorimatch i ES håndteres af BM25 på ``category_name.text``
(danish analyzer), ikke af synonym-udvidet dokumentprosa. Taber ES-siden
kategorifraserede eval-cases på det, er synonymer næste greb — målt,
ikke gættet.
"""

from __future__ import annotations

from typing import Any

DANISH_MONTHS = {
    1: "januar",
    2: "februar",
    3: "marts",
    4: "april",
    5: "maj",
    6: "juni",
    7: "juli",
    8: "august",
    9: "september",
    10: "oktober",
    11: "november",
    12: "december",
}


def build_embedding_text(source: dict[str, Any]) -> str:
    """Dokument-state (ES ``_source``) → dansk prosa.

    Tåler partielle dokumenter (categorized-før-created har hverken
    beløb eller dato) — udeladte felter udelades af prosaen.
    """
    tx_type = source.get("transaction_type") or ""
    amount = source.get("amount")
    type_label = "Indkomst" if tx_type == "income" or (tx_type == "" and (amount or 0) > 0) else "Udgift"

    parts = [type_label]
    if amount is not None:
        parts.append(f"paa {abs(float(amount)):.2f} kr")

    description = source.get("description")
    if description:
        parts.append(f"hos {description}")

    tx_date = source.get("tx_date")
    if tx_date:
        year, month, day = str(tx_date).split("-")
        parts.append(f"den {int(day)}. {DANISH_MONTHS[int(month)]} {year}")

    text = " ".join(parts) + "."

    category_name = source.get("category_name")
    if category_name:
        text += f" Kategori: {category_name}."
    subcategory_name = source.get("subcategory_name")
    if subcategory_name:
        text += f" Underkategori: {subcategory_name}."
    return text
