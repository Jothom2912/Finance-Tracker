// P2-39: browser-automatisering som ejet instrument.
// Se dev-notes/decisions/2026-07-28-browser-automation-instrument.md for hvorfor det
// tredje instrument findes: de 346 jsdom-tests og de 24 Python-e2e-tests var BEGGE
// grønne gennem hele P1-16, hvor hver bruger så "Failed to construct 'URL'" i stedet
// for data. jsdom håndhæver ikke CSP, og `curl` kører ikke klienten.
import { defineConfig, devices } from '@playwright/test';

// Adressen bor UDEN FOR `testDir`, fordi alt config'en importerer indlæses i
// config-konteksten — en fil derfra må ikke være en del af test-træet. Se filen.
import { BASE_URL } from './playwright.base-url.js';

export default defineConfig({
  // Uden for `src/`, fordi vitest ellers opsamler disse filer. Bemærk at det ikke er
  // nok i sig selv: vitests default-glob er repo-bred, så `vite.config.js` sætter
  // også et eksplicit `test.include`. Målt: uden det blev `npm test` rød.
  testDir: './e2e',

  use: {
    baseURL: BASE_URL,
    // Trace/video på fejl er hele grunden til at vi valgte @playwright/test frem for
    // pytest-playwright: det er det der afgør om en browser-suite bliver vedligeholdt
    // eller slukket, når den fejler i CI hvor ingen kan se skærmen.
    trace: 'retain-on-failure',
    video: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },

  // workers: 1 og retries: 0 er bevidste og hører sammen.
  //
  // Suiten deler ÉN session (e2e/fixtures/session.js), og perimeteren rate-limiter
  // /users/login og /users/register til 10r/m med burst=5 (nginx.conf:53-54, P2-27).
  // Parallelle workers ville hver registrere sin egen bruger og gøre 429 til en
  // flake-kilde der ligner en produktfejl.
  //
  // retries: 0 fordi en retry der skjuler flake er præcis samme fejlmode som en mock
  // der skjuler en bug — og det var den fejlmode der lod P1-16 nå master. Fejler suiten
  // ikke-deterministisk to gange uden kodeændring, ER det fundet: notér det, hæv ikke
  // retries.
  workers: 1,
  retries: 0,
  fullyParallel: false,

  // CI må ikke kunne blive grøn på nul tests. Python-e2e'ens conftest aborterer af
  // samme grund (tests/e2e/conftest.py) — en all-skipped suite exitter 0.
  forbidOnly: !!process.env.CI,

  reporter: process.env.CI
    ? [['list'], ['html', { open: 'never' }]]
    : [['list']],

  timeout: 30_000,
  expect: { timeout: 10_000 },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
