---
title: "Pattern: CSV parser registry"
updated: 2026-07-17
source: transaction-service doc; CLAUDE.md §CSV-import
---

# CSV parser registry

Bank CSV formats vary per bank; new banks must be addable **without touching the import
flow** (Open/Closed). One Protocol, concrete parser per bank, central registry.

## Shape (`services/transaction-service/app/application/csv_parsers/`)

- `base.py` — `BankCSVParser` Protocol (+ shared helpers in `utils.py`).
- `internal.py`, `nordea.py`, `danske_bank.py` — one implementation per format.
- `registry.py` — format key → parser; the import endpoint looks up, never branches on
  bank names.
- Frontend mirror: `config/bankFormats.js` is the single source for format options in the
  UI — never hardcode formats in components.

## Danish-format rules (handle explicitly, every parser)

UTF-8 BOM, semicolon separator, comma decimals, signed amounts. These are the recurring
bugs — a parser that "works" on a hand-made test file usually misses BOM or signs.

## Testing

**Golden file tests**: real (anonymized) CSV in, full expected parse out. Parsers are
deterministic transformations — golden files beat unit-testing individual fields
(CLAUDE.md §Test). Add a golden file with every new bank.

## Adding a bank

1. New `<bank>.py` implementing the Protocol; 2. register in `registry.py`;
3. golden file test; 4. add to `bankFormats.js`. No changes to `import_csv` itself.

## Related

- Dedup of imported rows is a separate concern —
  [import-dedup](import-dedup.md). CSV rows have no external id, so they use the fuzzy
  key; that asymmetry is deliberate (P2-09).
- Import flow detail:
  [transaction-service](../architecture/services/transaction-service.md) (note the open
  N+1-dedup-SELECT finding on the CSV path).
