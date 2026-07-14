"""Deterministic fixture dataset for the eval harness (AI-01).

~65 Danish transactions for eval users spanning 2026-03..2026-05. Every golden
answer (relevant ids, aggregation sums) derives from THIS data — change it and
the self-check test in test_golden_selfcheck.py tells you which cases drifted.

User 9001 is the primary eval user; 9002 exists only for the tenant-isolation
case.

Ids 1–72 are the original corpus (descriptions ASCII-transliterated, like
bank-CSV exports often are). Ids 100+ are DISTRACTORS added 2026-07-13 to
de-saturate the metrics before AI-20: semantically adjacent to the golden
queries (abonnement-but-not-streaming, bil-but-not-benzin, sundhed-but-not-
apotek, …) and written in real Danish orthography (æøå) so the eval also
exercises mixed-spelling retrieval. Distractor categories deliberately have
no CATEGORY_SYNONYMS entry — production taxonomies are never fully covered.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.adapters.outbound.transaction_client import TransactionDTO

EVAL_USER_ID = 9001
OTHER_USER_ID = 9002


def _tx(
    id: int,
    amount: str,
    category: str | None,
    description: str,
    d: date,
    *,
    user_id: int = EVAL_USER_ID,
    tx_type: str | None = None,
) -> TransactionDTO:
    return TransactionDTO(
        id=id,
        user_id=user_id,
        account_id=1 if user_id == EVAL_USER_ID else 2,
        account_name="Evalkonto",
        category_name=category,
        amount=Decimal(amount),
        transaction_type=tx_type or ("income" if Decimal(amount) > 0 else "expense"),
        description=description,
        date=d,
    )


EVAL_TRANSACTIONS: list[TransactionDTO] = [
    # --- Dagligvarer ---
    _tx(1, "-287.50", "Dagligvarer", "Netto", date(2026, 4, 15)),
    _tx(2, "-412.00", "Dagligvarer", "Foetex", date(2026, 4, 18)),
    _tx(3, "-156.75", "Dagligvarer", "Rema 1000", date(2026, 3, 28)),
    _tx(4, "-523.10", "Dagligvarer", "Bilka", date(2026, 3, 12)),
    _tx(5, "-98.25", "Dagligvarer", "Netto", date(2026, 5, 2)),
    _tx(6, "-176.00", "Dagligvarer", "Lidl", date(2026, 5, 9)),
    _tx(7, "-334.40", "Dagligvarer", "Netto", date(2026, 3, 5)),
    _tx(8, "-267.80", "Dagligvarer", "Rema 1000", date(2026, 4, 25)),
    # --- Restaurant / cafe ---
    _tx(10, "-245.00", "Restaurant", "McDonalds", date(2026, 3, 15)),
    _tx(11, "-189.00", "Restaurant", "Dalle Valle", date(2026, 4, 20)),
    _tx(12, "-62.00", "Restaurant", "Espresso House", date(2026, 4, 8)),
    _tx(13, "-58.00", "Restaurant", "Espresso House", date(2026, 5, 14)),
    _tx(14, "-312.50", "Restaurant", "Cafe Vivaldi", date(2026, 5, 21)),
    _tx(15, "-149.00", "Restaurant", "Wolt", date(2026, 4, 3)),
    # --- Transport ---
    _tx(20, "-350.00", "Transport", "DSB Pendlerkort", date(2026, 3, 1)),
    _tx(21, "-350.00", "Transport", "DSB Pendlerkort", date(2026, 4, 1)),
    _tx(22, "-350.00", "Transport", "DSB Pendlerkort", date(2026, 5, 1)),
    _tx(23, "-120.00", "Transport", "Rejsekort optankning", date(2026, 4, 12)),
    _tx(24, "-689.90", "Transport", "Circle K benzin", date(2026, 5, 6)),
    # --- Underholdning / abonnementer ---
    _tx(30, "-149.00", "Underholdning", "Netflix", date(2026, 3, 5)),
    _tx(31, "-149.00", "Underholdning", "Netflix", date(2026, 4, 5)),
    _tx(32, "-149.00", "Underholdning", "Netflix", date(2026, 5, 5)),
    _tx(33, "-119.00", "Underholdning", "Spotify", date(2026, 4, 10)),
    _tx(34, "-119.00", "Underholdning", "Spotify", date(2026, 5, 10)),
    _tx(35, "-99.00", "Underholdning", "HBO Max", date(2026, 4, 22)),
    _tx(36, "-79.00", "Underholdning", "Disney Plus", date(2026, 5, 22)),
    # --- Toej ---
    _tx(40, "-899.00", "Toej", "H&M", date(2026, 4, 10)),
    _tx(41, "-459.95", "Toej", "Zara", date(2026, 5, 17)),
    _tx(42, "-1250.00", "Toej", "Magasin", date(2026, 3, 20)),
    # --- Bolig / faste udgifter ---
    _tx(50, "-6500.00", "Bolig", "Husleje", date(2026, 3, 1)),
    _tx(51, "-6500.00", "Bolig", "Husleje", date(2026, 4, 1)),
    _tx(52, "-6500.00", "Bolig", "Husleje", date(2026, 5, 1)),
    _tx(53, "-843.00", "Bolig", "Oersted el", date(2026, 4, 15)),
    _tx(54, "-412.00", "Bolig", "HOFOR vand", date(2026, 5, 15)),
    # --- Sundhed / personlig pleje ---
    _tx(60, "-156.00", "Sundhed", "Apoteket", date(2026, 4, 14)),
    _tx(61, "-289.50", "Sundhed", "Matas", date(2026, 5, 3)),
    _tx(62, "-249.00", "Sundhed", "Fitness World", date(2026, 3, 1)),
    _tx(63, "-249.00", "Sundhed", "Fitness World", date(2026, 4, 1)),
    _tx(64, "-249.00", "Sundhed", "Fitness World", date(2026, 5, 1)),
    # --- Indkomst ---
    _tx(70, "28500.00", "Loen", "Loenoverfoersel", date(2026, 3, 31)),
    _tx(71, "28500.00", "Loen", "Loenoverfoersel", date(2026, 4, 30)),
    _tx(72, "1200.00", "Loen", "MobilePay fra Anders", date(2026, 4, 16)),
    # ================= Distractors (2026-07-13, ids 100+) =================
    # --- Telefon & internet: "abonnement" uden at være streaming ---
    _tx(100, "-199.00", "Telefon & internet", "Telia mobilabonnement", date(2026, 4, 3)),
    _tx(101, "-299.00", "Telefon & internet", "YouSee bredbånd", date(2026, 4, 20)),
    _tx(102, "-199.00", "Telefon & internet", "Telia mobilabonnement", date(2026, 5, 3)),
    # --- Forsikring: "regning" uden at være el/vand; "bil" uden at være benzin ---
    _tx(103, "-189.00", "Forsikring", "Tryg indboforsikring", date(2026, 4, 6)),
    _tx(104, "-540.00", "Forsikring", "Codan bilforsikring", date(2026, 5, 11)),
    # --- Hjem & indretning: "bolig"-nært uden at være husleje/el/vand ---
    _tx(105, "-134.50", "Hjem & indretning", "Søstrene Grene", date(2026, 4, 11)),
    _tx(106, "-1499.00", "Hjem & indretning", "IKEA", date(2026, 4, 26)),
    _tx(107, "-387.25", "Hjem & indretning", "Silvan byggemarked", date(2026, 5, 24)),
    # --- Shopping (ikke-tøj): distraherer "toej shopping" ---
    _tx(108, "-89.00", "Shopping", "Flying Tiger", date(2026, 5, 18)),
    _tx(109, "-249.95", "Shopping", "Bog & Idé", date(2026, 3, 22)),
    # --- Bil: værksted/medlemskab — ikke benzin, ikke offentlig transport ---
    _tx(110, "-2350.00", "Bil", "AutoMester værksted", date(2026, 4, 9)),
    _tx(111, "-660.00", "Bil", "FDM medlemskab", date(2026, 3, 16)),
    # --- Transport, men hverken tog/pendlerkort eller benzin (kun maj —
    #     april-aggregeringen for Transport skal forblive uændret) ---
    _tx(112, "-185.00", "Transport", "Taxa 4x35", date(2026, 5, 30)),
    # --- Restaurant: juicebar — relevant for "restauranter og cafeer",
    #     distractor for "kaffe" ---
    _tx(113, "-78.00", "Restaurant", "Joe & The Juice", date(2026, 4, 14)),
    # --- Kiosk: hverken supermarked eller restaurant ---
    _tx(114, "-45.50", "Kiosk", "7-Eleven Kbh H", date(2026, 3, 19)),
    # --- Underholdning uden at være streaming — kategorisynonymerne
    #     ("streaming, abonnement, film") gør netop disse docs til hårde
    #     distractors for "streaming abonnementer" ---
    _tx(115, "-260.00", "Underholdning", "Nordisk Film Biografer", date(2026, 4, 24)),
    _tx(116, "-155.00", "Underholdning", "Tivoli entré", date(2026, 5, 16)),
    # --- Sundhed uden at være apotek/fitness ---
    _tx(117, "-850.00", "Sundhed", "Tandlægehuset", date(2026, 4, 17)),
    _tx(118, "-1195.00", "Sundhed", "Louis Nielsen briller", date(2026, 3, 25)),
    # --- Personlig pleje ---
    _tx(119, "-420.00", "Personlig pleje", "Frisør Salon Saks", date(2026, 5, 27)),
    _tx(120, "-112.75", "Personlig pleje", "Normal", date(2026, 5, 4)),
    # --- Gaver ---
    _tx(121, "-325.00", "Gaver", "Interflora blomster", date(2026, 4, 29)),
]

OTHER_USER_TRANSACTIONS: list[TransactionDTO] = [
    _tx(900, "-500.00", "Dagligvarer", "Bilka", date(2026, 4, 12), user_id=OTHER_USER_ID),
    _tx(901, "-150.00", "Restaurant", "McDonalds", date(2026, 4, 19), user_id=OTHER_USER_ID),
]
