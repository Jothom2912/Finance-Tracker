---
date: 2026-07-28
topic: P3-23 — banking-service på uv + pyproject, med lockfile, dev-split og typecheck-gate
---

# Session 2026-07-28 — P3-23: banking på uv + pyproject

## Done

Fire commits, én logisk enhed hver:

- `6e9c8bda` — `pyproject.toml` + `uv.lock`, `requirements.txt` slettet, `makefile` på `uv run`,
  `sys.path`-løkken ud af `tests/conftest.py`. `python-jose` og `aiosqlite` til dev-gruppen.
- `6a998bc0` — `Dockerfile` på `uv sync --frozen --no-dev` med `PATH="/app/.venv/bin:$PATH"`.
- `0fd25d59` — `[tool.mypy]`, `typecheck`-target, `banking-service` i `TYPECHECK_SERVICES`,
  5 annotations-fixes + 9 ignores med item-referencer.
- Docs (denne log, planens Outcome, BACKLOG, STATUS, CLAUDE.md).

Målt resultat: install-sti **11 af 12** services, typecheck-gate **9 af 12**.

## Learned / surprised

**1. `python-jose` var en test-afhængighed i produktionsimaget.** Den bar P3-26's to CVE'er og
blev brugt på præcis ét sted: `tests/integration/test_bank_api.py:32`. App-koden signerer med
PyJWT. Den lå i runtime-listen udelukkende fordi der ikke var noget dev/runtime-split at lægge
den i. **Generaliseringen er værd at holde fast:** et manglende dev-split er ikke kun uryddeligt,
det er en angrebsflade — og den slags findes ved at spørge "hvem importerer faktisk denne pakke",
ikke ved at læse pin-listen. Skrevet ind i CLAUDE.md.

**2. Gaten genopdagede fire kendte items i den ene service den ikke dækkede.** 31 fejl i 8 filer,
og de klumpede sig: P2-32 (1), P2-33 (2), P2-35 (2), P2-36 (17 fejl på 3 linjer). Kun 5 var ægte
annotations-fejl. Det er *samme* udbytte-mønster som P2-31's egen udrulning (usande kontrakter,
ikke typefejl) — nu observeret to gange, hvilket gør det til en forventning snarere end en
anekdote. Konsekvens: en ny service på gaten skal budgetteres som *kontrakt-arkæologi*, ikke som
oprydning, og `# type: ignore  # P2-3x` er den rigtige udgang, fordi `warn_unused_ignores`
gør den selvoprydende.

**3. `tail -40` skjulte to mypy-fejl, og den ene modbeviste en kommentar jeg netop havde
skrevet.** Jeg skrev i en ignore at "the sibling `update_status` call types the same argument as
Optional — the two ports disagree about their own key". Da jeg kørte mypy uden trunkering, fejlede
`update_status` også: begge kræver `UUID`, portene er *enige*. Kommentaren blev rettet. Dette er
den samme fejlklasse som repoets `tail`-forbud, bare for *læsning* frem for exit-koder: en
trunkeret fejlliste er en usand fejlliste. Værd at sige eksplicit, fordi jeg havde skrevet en
plausibel forklaring på et mønster der ikke fandtes.

**4. En præeksisterende `# type: ignore` uden item-reference lå i `sync_scheduler.py:89`**
("rows fra DB har altid id"). Den var usynlig så længe mypy ikke kørte på servicen. Den er nu
mærket P2-35, som er den klasse den tilhører. Lektien: ignores i ikke-gatede services er
ubeskyttede påstande — de bliver først kontrakter når gaten når dertil.

**5. `psycopg2`-blokkeren i P3-39 fandtes ikke.** Rækken sagde at bankings deps bygger `psycopg2`
fra kilde og fejler på en almindelig macOS-boks, hvilket var begrundelsen for at suiten "kun
nogensinde har kørt i CI". Servicen har pinnet `psycopg2-binary` hele tiden. Suiten kørte lokalt
i første forsøg: 68 passed. Rækken er korrigeret.

## Open ends

- **CI har ikke kørt på dette.** `make verify-typecheck-gate` kræver en pushet kørsel og afviste
  derfor at bekræfte at banking nu er inde i gaten fra CI's side. Kontrollen er kørt *lokalt*
  (bevidst typefejl → `make typecheck` rød → fjernet), men CI-halvdelen af P2-31's Kontrol C
  mangler. **Næste skridt:** push, `make ci-status`, derefter `make verify-typecheck-gate` og
  bekræft at den rapporterer 9 gatede / 3 ikke-gatede.
- **`account-service` er nu ene tilbage** på `requirements.txt` uden lockfile og uden mypy. CI's
  `elif [ -f requirements.txt ]`-gren findes udelukkende for den; den kan dø sammen med P3-01.
  P3-39's effort er sænket til S, da kun account-halvdelen står.
- **En deprecation værd at kende, ikke handle på nu:** fastapi 0.140.7's testclient advarer
  `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install
  httpx2 instead`. Rammer alle services på nyere fastapi, ikke kun banking. Ikke filed —
  det bør være ét item på tværs, ikke ét per service.
- **`docs/security-audit-notes.md`** og frontendens `react-router-dom` 7.6.3 står stadig som
  P3-26's resterende halvdel, sammen med selve scanningen (dependabot/`pip-audit`).

## Notes updated

- **Ny:** `plans/2026-07-28-p323-banking-uv-pyproject.md` (+ Outcome), denne session-log.
- `backlog/BACKLOG.md` — P3-23 → done + detail-sektion; P3-39-rækken halveret og korrigeret
  (`psycopg2`-påstanden); P3-26's `python-jose`- og `fastapi`-halvdele lukket; P2-37's detail
  fik et efterskrift om at fælden ikke var armeret.
- `STATUS.md` — Active/Next up, og fire "Standing traps"-udsagn der var blevet usande
  (pip-uden-venv, "10 af 12", "de 4 udenfor", banking-kun-i-CI). Ny note om at P2-32/33/35/36
  hver har et fodfæste i banking nu.
- `CLAUDE.md` — 9 af 12 på gaten, 11 af 12 på én install-sti, undtagelseslisten reduceret til
  `account`, sætningen om at banking ikke var dækket af sin egen gate slettet, og to nye regler:
  forvent kontrakter frem for typefejl ved indrullering, og dev/runtime-split som
  sikkerhedsegenskab.
- `00-INDEX.md` — planen indekseret.
