// P2-39 test 2 — CSP'en håndhæves i APPEN, ikke kun i headeren.
//
// Forskellen er hele pointen. `curl -I` beviser at nginx sender headeren
// (nginx.conf:105); den siger intet om hvorvidt appen kan køre under den. Og de 346
// jsdom-tests kan aldrig sige det, fordi jsdom ikke håndhæver CSP overhovedet.
//
// Testen er samtidig P3-25's C2-kontrol i checket-ind form. Den ad hoc headless-probe
// dér fandt at `style-src 'unsafe-inline'` er tvunget af `react-remove-scroll`, men
// proben KUNNE IKKE KLIKKE — og scroll-locken opstår først når en dialog åbnes. Det
// klik er linje ~65 i denne fil.
//
// VERIFICERET RØD (2026-07-28), to mutationer i den KØRENDE container (`sed` i
// /etc/nginx/conf.d/default.conf + `nginx -s reload`; bemærk at `docker compose restart`
// IKKE gendanner filen — mutationen ligger i containerens writable layer, så det kræver
// `up -d --force-recreate`):
//   `style-src` uden 'unsafe-inline'  → 1 violation, `style-src-elem`/inline, ved
//     dialog-åbningen. 0 på /dashboard. Det er P3-25's C2 afgjort med et tal: direktivet
//     er nødvendigt, og præcis kun af den grund nginx.conf angiver.
//   `script-src 'none'`               → appen mounter ikke; testen rød på at kortet/dialogen
//     ikke findes, ikke på violations. Samme kontrol-udfald som P3-25 målte.
//
// Bemærk koblingen: assertionerne nedenfor kræver at læsestien virker, så en fejl i
// GraphQL-stien gør OGSÅ denne test rød. Det er bevidst — CSP målt på en tom side er
// trivielt nul violations — men læs test 1 først når begge er røde.
import { test, expect } from './fixtures/session.js';

// Lytteren skal hænge på før appens egne scripts kører, ellers går de violations vi
// leder efter tabt. `securitypolicyviolation` bobler til document.
const COLLECT_VIOLATIONS = () => {
  window.__cspViolations = [];
  document.addEventListener('securitypolicyviolation', (e) => {
    window.__cspViolations.push({
      directive: e.effectiveDirective || e.violatedDirective,
      blockedURI: e.blockedURI,
      source: `${e.sourceFile ?? '?'}:${e.lineNumber ?? '?'}`,
    });
  });
};

const readViolations = (page) => page.evaluate(() => window.__cspViolations ?? []);

/** Fejlbesked der siger hvad man skal GØRE, ikke kun at der var violations. */
const describe = (where, violations) =>
  `${violations.length} CSP-violation(s) på ${where}:\n` +
  violations.map((v) => `  ${v.directive} blokerede ${v.blockedURI} (${v.source})`).join('\n') +
  '\n\nEt direktiv i nginx.conf er strammet, eller et nyt bibliotek gør noget det ikke ' +
  'gjorde før. Løsn IKKE direktivet uden at måle hvilken mekanisme der kræver det — ' +
  'begrundelsen for hvert direktiv står i nginx.conf.';

test('appen kører uden CSP-violations, også når en radix-dialog åbnes', async ({ appPage }) => {
  await appPage.addInitScript(COLLECT_VIOLATIONS);

  // Fuld navigation, ikke client-side routing: init-scriptet kører per navigation, og
  // fixturen har allerede besøgt /dashboard uden lytteren.
  await appPage.goto('/dashboard');
  // Recharts' pie chart er det ene af de to steder nginx.conf udpeger som "brækker
  // først". Vent på et rigtigt kort, ikke på `load` — en tom side har trivielt nul
  // violations, og det er den grønne-på-ingenting-fælde hele itemet handler om.
  await expect(
    appPage.locator('.summary-card', { has: appPage.getByRole('heading', { name: 'Samlet indkomst' }) })
  ).toBeVisible();
  const onDashboard = await readViolations(appPage);
  expect(onDashboard, describe('/dashboard', onDashboard)).toEqual([]);

  await appPage.goto('/transactions');

  // Klikket. `react-remove-scroll` (radix' scroll-lock) laver et INLINE stylesheet via
  // createElement("style") + appendChild(createTextNode(...)) — den mekanisme
  // `style-src 'unsafe-inline'` findes for, og den findes ikke før dialogen åbner.
  await appPage.getByRole('button', { name: 'Tilføj ny transaktion' }).click();
  await expect(appPage.getByRole('dialog')).toBeVisible();

  const violations = await readViolations(appPage);
  expect(violations, describe('/transactions med åben dialog', violations)).toEqual([]);
});
