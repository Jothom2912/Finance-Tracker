---
title: Taksonomi-mutationer er internal-only, ikke rollestyrede
date: 2026-07-29
status: accepted
backlog: [P2-28]
supersedes: null
promoted-to-adr: null
---

# Taksonomi-mutationer er internal-only, ikke rollestyrede

## Decision

De seks skrive-ruter på den globale taksonomi flytter til `/api/v1/internal/…` bag
`require_internal_api_key`, som categorization-service allerede har. Ingen bruger-JWT kan
skrive i taksonomien. Læse-ruterne beholder sti, JWT-krav og svar-form.

Guarden sættes **router-level**, ikke per endpoint — samme begrundelse som
`categorize_router` (P1-15): en fremtidig rute på routeren er vagtet by default frem for
ved at huske at opt-in.

## Context

Fra [product-surface-sweepet](../findings/2026-07-26-product-surface-sweep.md) (SEC-5).
Sweepet formulerede problemet som `DELETE`, men undersøgelsen 2026-07-29 flyttede det:
`DELETE` er allerede vagtet i domænet (`CategoryHasSubcategories`, `SubCategoryInUse`,
`FALLBACK_SUBCATEGORY_NAME`). Den uvagtede fan-out er **`PUT`**, som har nul guards, fordi
intet bliver forældreløst af et rename og ingen "in use"-guard derfor kan fange det.

**Målt før ændringen, mod den kørende dev-stak:** en bruger registreret ét minut i forvejen
(id 466), som ejer **nul** transaktioner, kaldte `PUT /api/v1/categories/1` gennem
perimeteren, fik **200**, og `TaxonomyProjector.handle_category` →
`propagate_category_rename` omskrev derefter `category_name` på **150 docs fordelt på 23
andre brugere** i Elasticsearch — og nul af sine egne. Det er itemets
eksistensberettigelse, og det er et tal frem for en formodning.

Dertil er det en **shippet** feature, ikke kun en manglende dependency:
`CategoriesPage.jsx` tilbyder en "Administrer kategorier"-knap.

## Alternatives considered

- **`is_admin`-rolle** — afvist. Der findes hverken en admin-UI eller en måde at *tildele*
  rollen uden at røre DB'en direkte. Den ville altså give samme praktiske resultat
  (out-of-band administration) mod prisen af en user-migration og et JWT-claim som alle 12
  services ser. Filed som feature-item i stedet.
- **Per-bruger taksonomi** — afvist her, filed som feature-item. `categories.name` er
  globalt unique, og hver læse-sti i gateway/analytics/transaction rører den; det er en
  ejerskabsmodel-ændring, ikke en autorisations-ændring.
- **Kun vagte `PUT`** — afvist. `POST` og `DELETE` er også skriv i delt state, og en
  guard der dækker fem af seks ruter er en guard man skal huske grænsen for. Router-level
  koster ikke mere end per-endpoint.

To målinger bærer valget af internal-only:

1. **Perimeteren lukker `/api/v1/internal/*` gratis.** `nginx.conf:139` er en deny-backstop
   (`return 404`). Verificeret 2026-07-29 *før* kodeændringen:
   `GET /api/v1/internal/categories/1` på `127.0.0.1:3000` → **404**. Internal-only kræver
   derfor **nul** nginx-ændringer og er præcis den mekanisme ADR-0005 blev bygget til.
2. **Taksonomien har allerede en ejer-kontrolleret ændringssti** i migrationerne
   `002_seed_categories`, `003_seed_subcategories` og
   `006_heal_display_order_and_emit_taxonomy_seed_events`. Vi fjerner altså ikke den eneste
   måde at ændre taksonomien — vi fjerner den *utilsigtede* måde.

## Consequences

**Valget er reversibelt.** Guarden sidder router-level, så en senere `is_admin` er ét
linjeskift på routeren, ikke en omskrivning.

Frontendens `CategoryManagement`-modal slettes — den kan ikke blive stående og kalde ruter
der svarer 405. Det er den eneste irreversible del af diffen, og den er i git.

Et miljø uden `INTERNAL_API_KEY` får **503** på skrive-ruterne frem for 401 (P1-15's
bevidste fail-closed-valg). Det betyder at et sådant miljø ikke kan seede taksonomi via
API'et — men seeding sker via migrationer, så det er ikke en ny begrænsning. Nævnt her så
det ikke fejldiagnosticeres som "guarden virker ikke".

**Ikke ADR-materiale.** Det er en autorisationsbeslutning i én bounded context, ikke en
systemgrænse. ADR-003 (taksonomi-ejerskab) er urørt: denne beslutning handler om
*autorisation over* taksonomien, ikke *ejerskab af* den.
