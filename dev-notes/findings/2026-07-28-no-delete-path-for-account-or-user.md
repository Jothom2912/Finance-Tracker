---
title: Der findes ingen sletningssti for konti og brugere — soft-delete-konventionen gælder ikke de to entiteter der ejer alt andet
date: 2026-07-28
severity: LOW
status: open
scheduled-as: P2-41
related:
  - ../plans/2026-07-28-p239-browser-automation.md
  - ../plans/2026-07-28-p225-transaction-soft-delete.md
  - ../findings/2026-07-28-gateway-falls-back-to-first-account.md
---

# Der findes ingen sletningssti for konti og brugere

**`account-service` og `user-service` eksponerer ingen DELETE.** Målt på de kørende
services' egne OpenAPI-dokumenter, ikke på kode-læsning:

```
$ curl -s localhost:8004/openapi.json   # account-service
/api/v1/accounts/               ['get', 'post']
/api/v1/accounts/{account_id}   ['get', 'put']
/api/v1/account-groups/         ['get', 'post']
/api/v1/account-groups/{group_id} ['get', 'put']

$ curl -s localhost:8001/openapi.json   # user-service
/api/v1/users/register ['post']
/api/v1/users/login    ['post']
/api/v1/users/me       ['get']
/api/v1/users/{user_id} ['get']
```

Og `Account` har ikke engang en kolonne til det:

```
account_db=# \d "Account"
 idAccount | name | saldo | User_idUser | budget_start_day
```

Ingen `is_deleted`, ingen `deleted_at`. CLAUDE.md's regel — *"Soft-delete frem for
hard-delete på domain-entiteter"* — er altså ikke løsnet for de to entiteter; den er
**fraværende**. Transaktioner har den (P2-25, verificeret: `DELETE` → 204 → `is_deleted:
true` i `transactions_v2`), konti og brugere har ikke.

## Hvordan det blev fundet

P2-39 trin 8 skulle rydde P3-25's efterladenskaber: bruger 368, konti 370 + 371, fem
transaktioner. Planen sagde "slet dem" og antog at API'et kunne. Det kunne den ikke —
oprydningsscriptet ville have fået **405** på konti og bruger. Kun de fem transaktioner blev
ryddet, og de blev ryddet rent: event emitteret, ES fulgte med, `periodOverview` gik fra
25.000/1.629,75 til 0/0.

Det er værd at bemærke *hvad* der afdækkede det: et trin i en plan der forudsatte en
kapabilitet, ikke en gennemlæsning af servicen. Antagelsen havde overlevet planlægning,
review og godkendelse.

## Konsekvensen i praksis

1. **Dev-stakken kan ikke ryddes gradvist.** Enten `docker compose down -v` (alt), eller
   testdata akkumulerer. Hver verifikations-session efterlader brugere og konti permanent,
   og doc-counts i ES kan derfor ikke sammenlignes på tværs af sessioner — det er allerede
   noteret som en begrænsning i P3-25's session-log.
2. **Der er ingen GDPR-sti.** "Slet min konto" kan ikke besvares af systemet i dag. Det er
   den egentlige grund til at dette ikke kun er ryddelighed.
3. **DB-sletning er ikke et alternativ.** `Account` er projiceret ud i transaction-service,
   gateway og banking. En `DELETE FROM "Account"` emitterer ingen event, så projektionerne
   ville beholde rækken — fantom-rækker der aldrig self-healer, samme fejlmode som
   `project_es_phantom_rows`.

## Hvad der bør gøres

`is_deleted` på `Account` + `DELETE /api/v1/accounts/{id}` der soft-deleter og emitterer
`AccountDeletedEvent` (full state, jf. self-healing-consumer-mønstret). Brugersletning er
større — den rører alle tolv services — og hører i sit eget item.

Indtil da: bruger 368 og konti 370/371 **står** i dev-stakken. Det er ikke et valg, det er
det eneste tilgængelige udfald.
