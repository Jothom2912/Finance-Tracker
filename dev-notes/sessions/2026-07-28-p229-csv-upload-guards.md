---
date: 2026-07-28
topic: P2-29 — størrelses-, MIME- og rækkegrænser på CSV-upload
---

# Session 2026-07-28 — P2-29 CSV-upload-guards

## Done

Fire commits, i planens rækkefølge:

- `555ffd5e` — `CSV_MAX_BYTES`/`CSV_MAX_ROWS` i `config.py`, handler-guard
  (`_reject_unimportable_upload`) før `.read()`, rækkegrænse i `ParsedCSVResult.add_row` så de
  tre parsere deler én implementation. De funktions-lokale
  `CSVImportException`-imports i parserne hævet til modulniveau undervejs.
- `7f4c35ac` — `Content-Length`-middleware i `main.py`, metode-scopet til `POST`.
- `d0661ad1` — `tests/integration/test_csv_import_api.py`, 12 tests, endpointets **første**
  adapter-dækning. Integration 69 → 81.
- `4621ac2a` — frontend pre-flight i `handleCsvUpload` + `CSV_MAX_BYTES` i `bankFormats.js`.

Docs: [plan + Outcome](../plans/2026-07-28-p229-csv-upload-guards.md#outcome), SEC-7 i sweepet
markeret lukket med sine tre forældede henvisninger rettet, backlog-rækken `done`.

## Learned / surprised

**`du` kan ikke se starlettes spoolede upload — og det gjorde planens disk-måling ugyldig.**
Planen foreskrev `du -sh /tmp` før/efter for at vise at middleware'en sparer disk-skrivningen.
Målt: `du` viser 4 KB i *begge* tilfælde, også mens 150 MB er i luften, fordi `tempfile` bruger
`O_TMPFILE` — filen er unlinked og har ingen directory-entry. Med `df -k /tmp` pollet under
uploaden: Content-Length-stien 0 MB, chunked-stien **137 MB**. Lektien er generel: når man måler
"blev der skrevet til disk", er `du` det forkerte instrument for alt der bruger `tempfile`.
Bivirkningen var god — det accepterede chunked-hul er nu kvantificeret i stedet for kun navngivet.

**To guards der svarer samme statuskode kan skygge for hinanden, og det ser ud som død kode.**
En multipart-body er aldrig mindre end filen den bærer, så middleware'en vinder altid på en
normal request; handler-guarden ser derfor ubrugt ud. Den er det ikke — chunked upload uden
`Content-Length` passerer middleware'en, og handler-guarden er den der afviser. Testene skelner
lagene ved deres `detail`-strenge, så hvert lag har præcis de tests der bliver røde uden det
(**2 / 1 / 1**). Jeg gættede 3/2/6 undervejs; det var forkert, og kontrollen viste det.

**En handler-guard kører efter at dependencies er resolvet.** `Depends(get_transaction_service)`
kører før handler-kroppen, så selv en request der straks afvises med 415 har allerede fået en
DB-session. Ikke en korrekthedsfejl, men det er grunden til at DoS-halvdelen hører i middleware,
og det er hvorfor testfilen kræver Docker for tests der aldrig rører databasen.

**`app.database.engine`s connection pool er bundet til én event loop.** pytest-asyncio giver hver
test sin egen loop, så den anden test i en ny testfil dør med
`InterfaceError: another operation is in progress`. `test_transaction_list_api.py` havde allerede
mønsteret (per-test engine + `get_db`-override); jeg kopierede det ikke, fordi mine tests ikke
*lignede* DB-tests. Hvis nogen tilføjer en tredje API-testfil: start med at kopiere den fixture.

## Open ends

- **`csv_parsers/base.py` importerer nu `app.config`** — application-lagets første config-import
  i denne service (målt: 0 før). Bryder ikke `patterns/hexagonal-architecture.md`, som forbyder
  infrastruktur-imports i *domain*, og transaction-service har ingen archon-test. Men hvis
  application-laget skal holdes config-frit, er det her det rulles tilbage, og prisen er at
  rækkegrænsen så ikke er env-tunbar. Ikke afgjort — noteret bevidst.
- **F2-12** arver `tests/integration/test_csv_import_api.py` og kan nu ændre `errors`-fladen
  uden samtidig at være endpointets første test.
- **CI er ikke kørt endnu** på de fire commits. Alt herover er lokalt: `make check` grønt
  (ruff, mypy 42 filer, 195 unit + 81 integration), frontend 344 tests + lint grønt, og
  live-verifikationen på fuld compose-stak. Kør `make ci-status` før noget nyt startes.
- `E2E` (`make test-e2e`) er **ikke** kørt lokalt denne session — endpointet er ikke i E2E-suiten,
  men det er værd at bekræfte i CI.

## Notes updated

- `plans/2026-07-28-p229-csv-upload-guards.md` — ny, derefter `status: done` + Outcome
- `findings/2026-07-26-product-surface-sweep.md` — SEC-7 lukket, tre forældede henvisninger rettet
- `backlog/BACKLOG.md` — P2-29 → `done 2026-07-28`, detail-sektionen afstøvet
- `00-INDEX.md`, `sessions/00-SESSIONS.md`, `STATUS.md`
