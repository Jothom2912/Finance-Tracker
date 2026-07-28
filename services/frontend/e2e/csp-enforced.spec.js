// P2-39 test 2 — CSP'en håndhæves i APPEN, ikke kun i headeren.
//
// Forskellen er hele pointen. `curl -I` beviser at nginx sender headeren
// (nginx.conf:105); den siger intet om hvorvidt appen kan køre under den. Og de 346
// jsdom-tests kan aldrig sige det, fordi jsdom ikke håndhæver CSP overhovedet.
//
// Testen er samtidig P3-25's C2-kontrol i checket-ind form. Den ad hoc headless-probe
// dér fandt at `style-src 'unsafe-inline'` er tvunget af `react-remove-scroll`, men
// proben KUNNE IKKE KLIKKE — og scroll-locken opstår først når en dialog åbnes. Det
// klik er linje ~50 i denne fil.
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
