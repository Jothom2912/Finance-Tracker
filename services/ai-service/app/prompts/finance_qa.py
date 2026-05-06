"""4T's prompt template for grounded finance Q&A."""

from __future__ import annotations


def build_finance_qa_prompt(question: str, retrieved_transactions: list[dict]) -> str:
    context = _format_context(retrieved_transactions)
    return f"""TRAITS:
Du er en erfaren dansk finansraadgiver, der analyserer personlige transaktioner.
Du er praecis med tal, aerlig naar data mangler, og du svarer kun ud fra de
transaktioner, du faar vist.

TASK:
Besvar brugerens spoergsmaal udelukkende baseret paa TRANSAKTIONSDATA nedenfor.
Giv aldrig gaet. Hvis data ikke er nok til at svare sikkert, saa sig det tydeligt.
Lav simple beregninger naar det er relevant.
Naar du naevner en konkret transaktion, skal du referere til dato og beloeb.
Svar med maksimalt 4 korte saetninger.

TONE:
Professionel men uformel. Svar paa dansk. Brug danske kroner (kr) og konkrete tal.
Hold svaret kort og praktisk.

TARGET:
En privatperson uden regnskabsbaggrund, som vil forstaa sit forbrugsmoenster.

TRANSAKTIONSDATA:
{context}

BRUGERENS SPOERGSMAAL:
{question}

SVAR:"""


def _format_context(retrieved_transactions: list[dict]) -> str:
    if not retrieved_transactions:
        return "Ingen relevante transaktioner blev fundet."

    lines = []
    for index, item in enumerate(retrieved_transactions, start=1):
        metadata = item.get("metadata") or {}
        amount = float(metadata.get("amount", 0.0))
        transaction_type = "udgift" if bool(metadata.get("is_expense", False)) else "indkomst"
        lines.append(
            "[S{index}] dato={date}; type={transaction_type}; beloeb={amount:.2f} kr; "
            "kategori={category}; tekst={description}; transaction_id={transaction_id}".format(
                index=index,
                date=metadata.get("date", "unknown"),
                transaction_type=transaction_type,
                amount=amount,
                category=metadata.get("category", "unknown"),
                description=metadata.get("description", ""),
                transaction_id=metadata.get("transaction_id", "unknown"),
            )
        )
    return "\n".join(lines)
