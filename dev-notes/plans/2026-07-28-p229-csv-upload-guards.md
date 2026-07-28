---
title: "P2-29: størrelses-, MIME- og rækkegrænser på CSV-upload"
date: 2026-07-28
status: done
backlog-items: [P2-29]
related:
  - ../findings/2026-07-26-product-surface-sweep.md
  - ../backlog/FEATURES.md
---

# P2-29: størrelses-, MIME- og rækkegrænser på CSV-upload

## Goal

`POST /api/v1/transactions/import-csv` kan i dag ikke bringe transaction-service ned med en
stor fil. Tre grænser, hver med sit eget fejlbillede: **bytes** (afvis før `.read()`),
**rækker** (afvis under parse), og **transport** (afvis før body når disken).

Done når: (a) en fil over grænsen giver `413` med en dansk besked og processen lever videre —
målt på RSS, ikke antaget; (b) en fil med for mange rækker giver `400` med rækkeantallet i
beskeden; (c) en oversized upload med `Content-Length` afvises **før** starlette spooler den til
`/tmp`; (d) alle tre grænser er bevist i stand til at blive røde ved at fjernes igen.

## Context

Fra [product-surface-sweepet](../findings/2026-07-26-product-surface-sweep.md) §SEC-7. Fundets
kerne holder, men **tre af dets henvisninger er forældede og skal rettes med i denne
ændring** — samme greb som P2-25/P3-23:

| Fundet siger | Målt 2026-07-28 |
|---|---|
| `adapters/inbound/rest_api.py:107-116` | `rest_api.py:131-147`; `await file.read()` står på **:141** |
| parsere i `adapters/inbound/csv_parsers/` | de bor i **`app/application/csv_parsers/`** (nordea `:34`, danske_bank `:35`, internal `:34`) |
| "doubled footprint" | **tre** samtidige kopier ved peak — se nedenfor |

**Hvor hukommelsen faktisk sprænger.** FastAPI parser multipart *før* handleren kaldes, og
`UploadFile` er en `SpooledTemporaryFile` med 1 MiB grænse — så en stor body er allerede spoolet
til `/tmp` når vi træder ind i funktionen. Det betyder to ting, og de peger hver sin vej:

1. `file.size` er kendt og **troværdig** når handleren kører. Den er talt af parseren ud fra
   modtagne bytes, ikke læst af en klient-header. En check på den er ikke kosmetik.
2. Selve RAM-eksplosionen er `await file.read()` (`:141`) → ét `bytes`-objekt på N, derefter
   `_decode()` → en `str`, derefter `io.StringIO(text)` → endnu en kopi. **Tre levende kopier
   ved peak.** Et `file.size`-check *lige før* `.read()` ligger altså præcis hvor fejlen er, og
   lukker hukommelses-halvdelen helt.

**Hvor alvorligt, konkret.** `k8s/apps/transaction-service.yaml:42` sætter
`limits.memory: 512Mi`. Med tre kopier OOM-dræbes poden omkring en ~150 MB fil — af én
authenticated bruger, for alle andre. I compose findes der *ingen* `mem_limit` på servicen
(kun på elasticsearch, `docker-compose.yml:93`), så lokalt rammer det værten i stedet. Det er
en driftsdetalje for verifikationen, ikke for fixet.

**Der er ingen perimeter at lægge grænsen i.** Målt: `services/frontend/nginx.conf` er 13
linjer og server kun SPA'en — API-trafik går aldrig gennem den. `k8s/` har **ingen** Ingress.
`transaction-service/Dockerfile:29` starter uvicorn uden `--limit-*`. Grænsen skal derfor bo i
applikationen. Det er præcis P3-24's observation, men P2-29 er **ikke blokeret** af den: en
in-app grænse er rigtig uanset hvordan perimeter-ADR'en lander, og skal ikke fjernes igen.

**Endpointet er det eneste af sin slags i repoet.** `UploadFile` optræder kun på
`rest_api.py:5,132`. Derfor bliver dette *ikke* en `shared/`-middleware — der er ingen anden
forbruger, og `shared/auth` er i dag den eneste delte FastAPI-flade.

**Der findes ingen adapter-tests for endpointet.** `tests/unit/test_transaction_service.py`
(`:818,844,862,870`) kalder `service.import_csv(...)` direkte med `bytes` og mocket UoW.
Ingen test POSTer nogensinde til `/import-csv`. Grænserne her er transport-adfærd, som den
eksisterende testform per konstruktion ikke kan se — så trin 4 er endpointets **første**
adapter-dækning, ikke bare nye cases.

## Beslutninger truffet før planen (2026-07-28)

**1. Håndhævelse i to lag, ikke tre.** Aftalt scope:

- **Handler-check på `file.size`** før `.read()` — lukker OOM'en, som er den der dræber
  processen for alle.
- **Middleware-check på `Content-Length`** — afviser før body skrives til `/tmp`. Browsere
  sætter altid headeren for `FormData`, så det dækker den reelle klient.
- **Ikke** stream-tælling af bytes for chunked/løgnagtig `Content-Length`.
  *Trade-off, accepteret eksplicit:* det hul lader en håndrullet klient fylde `/tmp` op til
  containerens disk. Det er bounded, det rammer ikke andre services, og det overlever en
  restart — hvorimod OOM'en dræber processen. Prisen for at lukke det er at middleware'en skal
  konsumere og videresende body'en, og at et afslag før body er læst giver `ECONNRESET` hos
  nogle klienter i stedet for en læsbar `413`. Skriv hullet ned i planens Risks, så det er
  afklaret frem for upræcist.

**2. MIME-checket er et tastefejls-filter, ikke en sikkerhedsgrænse — og allowlisten skal
være tolerant.** `file.content_type` er klient-leveret. Windows sender
`application/vnd.ms-excel` for `.csv` når Excel er registreret som handler, og flere browsere
sender `application/octet-stream`. En stram `text/csv`-only allowlist ville afvise ægte danske
bank-eksporter. Allowlisten bliver derfor `text/csv`, `application/csv`, `text/plain`,
`application/vnd.ms-excel`, `application/octet-stream` — hvilket er så bredt at det kun fanger
"jeg valgte en PDF ved en fejl". **Den rigtige validering findes allerede**: parserens
required-columns-check (`nordea.py:41-46`) afviser alt der ikke er den forventede CSV, med
`400`. Dette skal stå som kommentar i koden, så ingen senere forveksler MIME-checket med en
grænse man kan stole på.

**3. Rækkegrænsen er den bindende i praksis, ikke byte-grænsen.** Målt på fixturene:
`nordea_sample.csv` er 536 B / 7 linjer ≈ **76 B pr. række**. 10 MiB rummer altså ~137 000
rækker. En realistisk dansk bank-eksport — 5 år à ~50 tx/md — er ~3 000 rækker ≈ 230 KB, dvs.
~40× headroom. Konklusionen: **byte-grænsen fanger den patologiske enkelt-kæmpe-linje,
rækkegrænsen fanger den store-men-velformede fil.** De er ikke redundante, og rækkegrænsen er
den der oftest bider. Den beskytter et andet mål: ét `bulk_create` plus ét outbox-batch på
N rækker i **én** transaktion (`service.py:378-400`). P3-15 chunkede kun den interne saga-sti.

Valgte tal, med begrundelse frem for rundt tal: `CSV_MAX_BYTES = 10 * 1024 * 1024`
(3 kopier ≈ 30 MiB, ~6 % af podens 512Mi) og `CSV_MAX_ROWS = 50_000` (~17× den realistiske
eksport, og et outbox-batch der stadig committer).

**4. Byte- og MIME-afslag rejses som `HTTPException` i adapteren; rækkegrænsen som
`CSVImportException`.** CLAUDE.md foreskriver domain-exceptions med eksplicit HTTP-mapping —
det brydes ikke her, det afgrænses. Byte- og MIME-checket udtrykker ingen domæneregel og
rammer før application-laget overhovedet nås; de er transport, og `413`/`415` rejses direkte.
Rækkegrænsen er derimod en regel om *indholdet*, den opstår inde i parseren, og den skal nå
brugeren i det `errors`-felt hun allerede får — så den genbruger `CSVImportException` og dens
eksisterende mapping til `400` (`main.py:54-56`), uden ny wiring.
*Alternativet* — en ny exception mappet til `413` — ville være mere korrekt HTTP og koste et
handler-par; afvist fordi `400` med rækkeantallet i beskeden er lige så handlingsbar for
brugeren.

**5. Rækkegrænsen håndhæves i `ParsedCSVResult`, ikke i hver parser.** Alle tre parsere har
den samme `result.rows.append(...)`-løkke. En `add_row()`-metode på dataclassen i
`csv_parsers/base.py:8-19` der rejser ved overskridelse giver **ét** sted at ændre, og
`BankCSVParser`-protokollen bærer typen i forvejen. `registry.py:7` importerer allerede
`CSVImportException` på modulniveau, så der er ingen cykel — de funktions-lokale imports i
`nordea.py:37,44` er inkonsistens, ikke en cykel-workaround. Ryd dem op i samme trin.

**6. Frontendens grænse er UX, serverens er håndhævelse — og de får lov at drifte.**
En pre-flight-check i `handleCsvUpload` (`TransactionsPage.jsx:204-223`) sparer brugeren en
30-sekunders upload for at få en fejl (`apiClient.jsx:4,35-36` har en 30 s `AbortController`).
Konstanten duplikeres i `src/lib/bankFormats.js` — det er *det* centrale CSV-import-config-modul
konventionen udpeger, frem for at opfinde et modul til én konstant.
*Trade-off:* to tal kan komme ud af sync. Accepteret, fordi serveren er autoritativ og
fejlmoden ved drift er en let forkert klient-besked, ikke en omgåelse.

## Non-goals

- **Ingen ændring i hvad en gyldig import gør.** Under grænserne skal `imported`, `skipped`,
  `duplicates_skipped` og `errors` være bit-for-bit som i dag; dedup-nøglen
  `(user_id, account_id, date, amount, description)` røres ikke.
- **Ingen streaming-parser.** `.read()`-til-`bytes` bliver stående; vi begrænser N frem for at
  omskrive tre parsere og `BankCSVParser`-protokollen.
- **F2-12 (dry-run + per-row error report) er ude af scope.** Backloggen kalder det "one visit
  to that code path", men det sparer læsning af filen, ikke risiko: F2-12 er en produkt-ændring
  med egen UI-flade og egen verifikation, og samlet med dette bliver det svært at se hvilken
  halvdel der brød hvad. Den arver til gengæld en testfil at hænge sig på.
- **Ingen perimeter-arbejde.** P3-24 forbliver åben og uændret; intet her foregriber ADR'en.
- **`/transactions/bulk` røres ikke.** Den er JSON og internal-only, og har sin egen historie
  i P3-15/P2-09.

## Steps

1. [x] **Konstanter i config** — `app/config.py`: `CSV_MAX_BYTES: int = 10 * 1024 * 1024` og
   `CSV_MAX_ROWS: int = 50_000`, efter mønsteret fra `CATEGORIZATION_TIMEOUT_S: float = 0.5`
   (`:17`). Ingen `.env`-ændring; defaults er bevidst brugbare.

2. [x] **Handler-guard** — `app/adapters/inbound/rest_api.py:131-147`: før `await file.read()`,
   afvis på `file.content_type` udenfor allowlisten (`415`) og på
   `file.size is not None and file.size > CSV_MAX_BYTES` (`413`, med grænsen i MiB i den danske
   besked). Kommentar der siger at MIME-checket er et tastefejls-filter og at parseren er den
   rigtige validering. Bemærk `file.size` er `int | None` — servicen er på typecheck-gaten, så
   `None`-grenen skal være eksplicit, ikke antaget bort.

3. [x] **Rækkegrænse i én kilde** — `app/application/csv_parsers/base.py`: `add_row()` på
   `ParsedCSVResult` der rejser `CSVImportException` ved `CSV_MAX_ROWS`; de tre
   `result.rows.append(...)` i `nordea.py`, `danske_bank.py`, `internal.py` skiftes til den, og
   de funktions-lokale `CSVImportException`-imports i `nordea.py:37,44` hæves til modulniveau.
   Diff-form: én ny metode, tre en-linjers, to flyttede imports.

4. [x] **Content-Length-middleware** — `app/main.py`, efter `CORSMiddleware` (`:30-36`): afvis
   `POST` med `Content-Length > CSV_MAX_BYTES` med `413` før routing. Bevidst rute-agnostisk og
   metode-snæver, så den ikke bliver en generel body-grænse for JSON-endpointerne.

5. [x] **Første adapter-dækning af endpointet** — ny
   `tests/integration/test_csv_import_api.py`, der POSTer multipart: happy path (grænserne
   påvirker ikke en gyldig fil), `413` på oversize, `415` på forkert MIME, `400` med
   rækkeantal på for mange rækker, `text/csv`-varianterne accepteres, og `file.size is None`
   falder tilbage på at blive læst. Testen skal generere den store fil, ikke committe den.

6. [x] **Frontend pre-flight** — `CSV_MAX_BYTES` i `src/lib/bankFormats.js`; størrelses-check i
   `handleCsvUpload` (`TransactionsPage.jsx:204-223`) med dansk besked før `FormData` bygges.
   `api/transactions.jsx:66-93` røres ikke.

7. [x] **Ret de forældede henvisninger** — sweepets §SEC-7 (`:186-196`) får de tre målte
   rettelser fra Context-tabellen, backlog-rækken P2-29 (`BACKLOG.md:79`) og dens detail-sektion
   (`:235-237`) opdateres til `done` + link hertil, og `00-INDEX.md` får plan-linjen.

Commits: ét per trin 1-3 samlet (guards), ét for trin 4, ét for trin 5, ét for trin 6, ét for
trin 7 — per konventionen om commit per logisk fase.

## Verification

**Statisk:** `make -C services/transaction-service test`,
`make -C services/transaction-service typecheck` (servicen er på gaten, 9 af 12),
`make -C services/transaction-service lint`. Ikke pipet gennem `tail`.

**Kontrol, ikke kun treatment** — den del der gør målingen sand:

- Fjern handler-guarden igen → `413`-testen skal fejle. Fjern `add_row`-checket → rækketesten
  skal fejle. Fjern middleware'en → dens test skal fejle. Navngiv det forventede antal fejlende
  tests *før* kørslen.
- **Bevis at OOM'en var virkelig, ikke formodet.** Sæt midlertidigt `mem_limit: 512m` på
  transaction-service i compose (matcher k8s' `limits.memory`, og undgår at et lokalt forsøg
  rammer værten, da servicen i dag ikke har nogen). Med guarden **fjernet**: POST en ~150 MB
  CSV → containeren OOM-dræbes. Med guarden på: `413` inden for millisekunder, container op,
  RSS uændret målt med `docker stats` før/efter. Det er den ene måling der afgør om itemet var
  værd at lave.
- **Bevis at middleware'en sparer disken, ikke bare svarer 413.** `docker exec ... du -sh /tmp`
  før og efter en oversized POST *med* `Content-Length`: uændret. Samme POST med kun
  handler-guarden aktiv: `/tmp` vokser med filens størrelse og falder igen. Det er forskellen
  mellem de to lag, og den er ellers usynlig.

**Ægte fil, ikke kun genereret:** importér `tests/unit/fixtures/nordea_sample.csv` gennem UI'et
og bekræft at tallene er uændrede — non-goal 1 er den eneste måde at se en regression i det
normale flow.

**E2E:** `make test-e2e` (24 passed er baseline).

## Risks & rollback

| Risiko | Hvordan den opdages | Modtræk |
|---|---|---|
| Grænsen er for lav og afviser en ægte flerårig eksport | Bruger får `413` på en legitim fil | Tallet er målt til ~40× en 5-års-eksport og er en `Settings`-værdi — hæves via env uden deploy af kode |
| Middleware-afslag før body er læst giver `ECONNRESET` i stedet for læsbar `413` | Frontend viser generisk netværksfejl i stedet for den danske besked | Fanges i trin 5's test, som asserter på *status og body*; falder den, er modtrækket at lade handler-guarden være den brugervendte og middleware'en kun DoS-værn |
| MIME-allowlisten er for stram på en OS/browser-kombination vi ikke testede | `415` på en gyldig `.csv` | Allowlisten inkluderer bevidst `application/octet-stream`; sidste udvej er at gøre checket til en warning-log frem for et afslag |
| `add_row()` ændrer en parsers adfærd utilsigtet | Golden-file-parsertesterne (`test_nordea_parser.py`, `test_danske_bank_parser.py`, `test_csv_parsers.py`) | De findes allerede og skal være grønne uændrede — de er kontrollen på trin 3 |
| Chunked upload uden `Content-Length` fylder `/tmp` | Ikke overvåget i dag | **Accepteret, ikke løst** — se beslutning 1. Bounded af containerens disk, overlever restart |

**Rollback:** hvert trin er sit eget commit og er uafhængigt reverterbart. Trin 1-3 er additive
guards uden schema- eller kontraktændring, så en revert kan ikke efterlade data i en ny
tilstand — modsat P2-25 er der **ingen migration** her.

## Outcome

**Landet 2026-07-28 over fire commits**, i planens rækkefølge: `555ffd5e` (trin 1-3: config,
handler-guard, `add_row`), `7f4c35ac` (trin 4: middleware), `d0661ad1` (trin 5: 12 tests,
integration 69 → 81), `4621ac2a` (trin 6: frontend pre-flight). Ingen migration, intet
schema rørt.

**Alvorligheden var virkelig, og det er nu målt frem for formodet.** Med `mem_limit: 512m`
(k8s' tal) og `CSV_MAX_BYTES` hævet via env — samme image, én variabel ændret, altså en
ægte kontrol frem for et separat build — giver en 150 MB upload
`OOMKilled=true, ExitCode=137`; RSS gik fra 68,94 MiB til død. Med guarden på: **413 på 3 ms**,
RSS 82,26 → 82,41 MiB (støj), container oppe, `RestartCount=0`. Det var det ene tal der
afgjorde om itemet var værd at lave.

**Testfilen som kontrol pr. guard, med et tal jeg forudsagde forkert.** Planen sagde ikke
hvor mange tests hver guard ejede; jeg gættede 3/2/6 undervejs, og det faktiske er
**2 / 1 / 1**: handler-guard fjernet → 415-testen + chunked-413-testen; middleware fjernet →
kun middleware-testen; rækkegrænse fjernet → kun rækketesten. At middleware-testen *ikke*
falder når handler-guarden fjernes er selve pointen — middleware'en fanger den sag.

**De to lag er faktisk to lag, verificeret både i test og live.** Bekymringen var reel: en
multipart-body er aldrig mindre end filen den bærer, så middleware'en vinder altid på en
normal request, og handler-guarden ville se ud som død kode. Chunked upload skiller dem.
Live på fuld stak, samme 150 MB fil:

| Sti | Svar | Fra hvilket lag |
|---|---|---|
| Med `Content-Length` | 413 på 3 ms | middleware — `"Forespørgslen er for stor"` |
| `Transfer-Encoding: chunked` | 413 på 0,9 s | handler — `"CSV-filen er for stor"` |

**Planens egen disk-måling var et forkert instrument, og det ændrer hvad vi ved.** Planen
foreskrev `du -sh /tmp` før/efter. Målt: `du` viser **4 KB i begge tilfælde**, også mens 150 MB
var i luften — fordi `tempfile` bruger `O_TMPFILE`, så starlettes spoolede fil er unlinked og
har ingen directory-entry at tælle. Med `df -k /tmp` i stedet, pollet *under* uploaden:
Content-Length-stien bruger **0 MB**, chunked-stien bruger **137 MB**. Så:

- Middleware'ens værdi er bekræftet: den sparer hele disk-skrivningen for den reelle klient.
- **Det accepterede hul er nu kvantificeret, ikke kun navngivet:** chunked uden
  `Content-Length` koster ~filens størrelse i unlinked disk før handler-guarden afviser.
  Beslutning 1 står uændret — det er bounded og overlever restart — men prisen er målt.

**Non-goal 1 holdt:** `nordea_sample.csv` importerede live med
`{"imported":6,"skipped":0,"duplicates_skipped":0,"errors":[]}`, og en PDF gav 415 med den
danske besked. `make check` grønt: ruff, mypy (42 filer), 195 unit + 81 integration.

**To ægte forhindringer i testarbejdet, begge værd at kende:**

1. `app.database.engine` bygges ved import og pooler asyncpg-forbindelser bundet til den
   event loop der åbnede dem. pytest-asyncio giver hver test sin egen loop, så den anden test
   dør med `InterfaceError: another operation is in progress`. Løsningen — per-test engine +
   `get_db`-override — er den `test_transaction_list_api.py` allerede brugte; jeg havde ikke
   kopieret den, fordi mine tests ved første øjekast ikke *lignede* DB-tests.
2. **Guarden kører efter at en DB-session er anskaffet.** `Depends(get_transaction_service)`
   resolves før handler-kroppen, så selv en request der er ved at blive afvist med 415 har
   allerede fået en session. Det er ikke en korrekthedsfejl, men det er en grund mere til at
   middleware'en (som kører før routing) bærer DoS-halvdelen.

**Afveget fra planen:** `HTTP_413_REQUEST_ENTITY_TOO_LARGE` er deprecated i starlette 0.52 —
skiftet til `HTTP_413_CONTENT_TOO_LARGE`. Ellers ingen afvigelser.

**Nyt mønster indført, værd at bemærke:** `csv_parsers/base.py` importerer nu `app.config`.
Det er application-lagets **første** import af config i denne service (målt: 0 før). Det
bryder ikke `patterns/hexagonal-architecture.md`, som forbyder infrastruktur-imports i
*domain*, og transaction-service har ingen archon-test — men hvis application-laget skal
holdes config-frit, er dette stedet at rulle tilbage, og prisen er at rækkegrænsen så ikke
er env-tunbar.

**Follow-ups:** ingen nye items. F2-12 arver en testfil at hænge sig på
(`tests/integration/test_csv_import_api.py`) og kan nu ændre `errors`-fladen uden at være
endpointets første test. P3-24 er uberørt.
