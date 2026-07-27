---
date: 2026-07-27
topic: P2-31 — mypy som hård gate på 8 af 12 services; hvad gaten fandt, og hvad den ikke ser
---

# Session 2026-07-27 — P2-31 statisk typecheck som gate

Detaljerne per trin og per service står i
[planen](../plans/2026-07-27-p231-static-typecheck-gate.md) og dens Outcome; denne log er
historien om hvordan det gik, og de lektier der ikke hører til ét enkelt trin.

## Done

- `67c29dcc` + `617bbc11` — `py.typed` på `shared/domain` og `shared/messaging` + versionsbump,
  så markøren faktisk nåede de installerede kopier. Trin 1, og forudsætningen for alt det andet.
- `4b09ecd7` — analytics som pilot; rodens `pyrightconfig.json` slettet.
- `de39bb6f` — typecheck-gate i `python-services`-matrixen, allowlist starter på analytics.
- `9dec9338` — CI dækker nu `shared/domain`; dens 42 tests havde aldrig kørt.
- `69a8ac6a` — `make verify-typecheck-gate` + `scripts/verify_typecheck_gate.py` (kontrol C).
- 7 services mere på gaten: user `b63962ca`, notification `0295ab98`, ai `508c20ab`,
  budget `7d938fdb`, saga `9c2e59b3`, transaction `0642bc67`, categorization `302cc437`.
- Fix i shared undervejs: `7f071ba3` (`SerializableEvent` mod frozen `BaseEvent`),
  `f7fc0e9f` (`init_typed`).
- `71476703` — budget-services 204-ruter døde ved import i imaget; grøn gate, dødt image.
- `4fb0410f` + `36428508` — CLAUDE.md ikke længere ASPIRATIONAL, backlog lukket, P3-41 korrigeret.
- Seks nye backlog-items ud af bølgen: P2-32, P2-33, P2-34, P2-35, P2-36, P2-37.

## Learned / surprised

- **Fejltællinger rangerer ikke arbejde.** transaction-service havde 26 fejl, men de var
  **6 rødder**, og 20 af dem var én rod — `x-retry-count` læst fem steder på fire måder, hvor
  to af læsningerne kaster `TypeError` inde i en `except Exception`-retry-handler og dermed
  konverterer en enkeltstående handler-fejl til uendelig redelivery. Det var den vigtigste ting
  i hele bølgen, og et fejl-*antal* ville have sorteret servicen som "middel".
- **Tre gange samme lektie: en måling der ikke kan skifte værdi er ikke en måling.**
  (1) Baseline-tabellen blev målt med `MYPYPATH` mod kildetræet, hvilket får mypy til at
  analysere `domain` som source uanset `py.typed` — så gen-målingen efter trin 1 gav identiske
  tal, og jeg læste det først som "py.typed havde ingen effekt". (2) I saga blev
  `disallow_untyped_defs` probet med et `str.replace` på en anchor der ikke fandtes — en tavs
  no-op, så "ingen ny fejl" betød "ingen ny kode". (3) Selve gate-verifikationen kunne kun
  bevises ved at gøre den rød med vilje. **Spørg altid hvad målingen ville vise hvis
  hypotesen var falsk, før du læser resultatet.**
- **En blød afvigelse i værktøjet kan slukke den check den skulle skærpe.** `pydantic.mypy`
  *uden* `init_typed` syntetiserer et `__init__` hvor alle felter er `Any` — men pydantic v2
  bruger `dataclass_transform`, så mypy typer model-konstruktion nativt i forvejen. Pluginet
  **erstattede** altså en skarp native check med `Any` i hele user-service. Sporet var to
  `type: ignore` som pluginet afmeldte, fanget af `warn_unused_ignores`. Regressionen var i
  dækningen, ikke i koden — dvs. usynlig for enhver test.
- **Ignores skjuler hinanden.** `# type: ignore[assignment]` slår typen fast for alle senere
  kald på samme navn. Kun saga-service kunne se `SerializableEvent`-fejlen, fordi budget og user
  kalder gennem egen port hvor P2-32-ignoren står. Én begrundet ignore skjulte en anden,
  urelateret usand kontrakt — argumentet for at ignores skal være smalle og talte.
- **Makefile-fælde:** `check: lint format-check ## kommentar` har sine prerequisites *før*
  `##`. Et `typecheck` tilføjet efter kommentaren ser rigtigt ud i diffen og kører aldrig.
  Verificér med `make -n check`, ikke ved at læse filen.
- **Udbyttet var usande kontrakter, ikke typefejl.** Ingen af de fem vigtigste fund var
  "glemt annotation" — de var steder hvor den erklærede kontrakt var forkert og koden derfor
  aftalte noget andet end den påstod. Det er en anden og bedre begrundelse for gaten end
  "færre TypeErrors", og den er værd at bruge til eksamen: en typecheck er en
  kontrakthåndhæver, ikke en crash-forebygger.
- **Gaten er ikke den samme checker på tværs af services.** notification låser mypy 2.3.0,
  analytics 2.1.0. Ikke et problem i dag, men det betyder at "grøn på min service" ikke er
  transitivt.

## Open ends

- **P2-37 er den akutte** — bølgens sidste fejl var en grøn `make check` og et dødt image,
  fordi tests læser `uv.lock` og imaget `requirements.txt`. Tredje gang i ét item at checken og
  virkeligheden læste fra hver sin kopi. Målt 2026-07-28: drift-betingelsen findes i **præcis
  én** service (budget har begge filer), de 9 uv-services bygger med `uv sync --frozen` og kan
  ikke drifte, og de tre `make freeze`-targets der findes sidder alle på services der ikke
  bruger dem.
- **P3-23 er blokkeren for at gaten dækker den service fejlen var i.** banking mangler
  `pyproject.toml` → kan ikke komme på allowlisten. Uændret ved lukning.
- **De fire udenfor:** goal (P2-34), banking + account (P3-23/P3-39), gateway (98 fejl, eget
  item). Antag ikke at en typefejl er fanget dér.
- **`tests/` er ikke dækket** på nogen af de 8 (`packages = ["app"]`) — 131 testfiler. Det gør
  P3-41 (`spec=` på mocks) til den eneste kontrol der findes inde i `tests/`, og dens
  oprindelige "P2-31 først"-begrundelse er dermed opfyldt og udtømt. Alternativet — tag
  `tests/` med i mypy-scope — bør vejes mod P3-41 frem for antages underlegent.
- **26 begrundede ignores** står i koden. De er kun forsvarlige fordi `warn_unused_ignores`
  får dem til at fejle af sig selv når fixet lander; det er den mekanisme der skal holde.

## Notes updated

- Ny: denne session-log; Outcome-sektion tilføjet planen (2026-07-28).
- Opdateret: `findings/2026-07-27-sync-trigger-double-value.md` (resolved),
  `backlog/BACKLOG.md` (P2-31 done + P3-41 korrigeret), `CLAUDE.md`, `STATUS.md`.
- Nye findings ud af bølgen: outbox-port-declares-foreign-entity,
  internal-api-key-optional-but-mandatory, goal-entity-two-runtime-types,
  optional-id-hides-unpersisted-entity, serializable-event-demands-mutable-attrs,
  retry-header-read-five-ways, none-annotation-204-fastapi-split.
