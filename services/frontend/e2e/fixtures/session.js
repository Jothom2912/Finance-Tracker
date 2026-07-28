// P2-39: fixturen der ejer session-seedingen.
//
// Den findes fordi seedingen har en fælde der ikke fejler. `authStorage.js:1` erklærer FEM
// nøgler, men `AuthContext.jsx:17-35` kræver kun tre af dem for at anse brugeren for logget
// ind. Uden `account_id` sender `apiClient` ingen `X-Account-ID` (apiClient.jsx:13-14), og
// `periodOverview` svarer med **tavse nuller i stedet for en fejl** — altså en test der ser
// grøn ud på en tom app. Målt under P3-25. Den slags må ikke ligge i hver spec.
//
// Fixturen er worker-scoped: hele suiten deler én bruger og én session. Det er ikke en
// optimering, det er perimeteren — nginx rate-limiter /users/login og /users/register til
// 10r/m med burst=5 (nginx.conf:53-54, P2-27), så en per-test-registrering ville gøre 429
// til en flake-kilde der ligner en produktfejl.
import { test as base, request as apiRequest, expect } from '@playwright/test';

import { BASE_URL } from '../../playwright.base-url.js';

// Præcis de nøgler `authStorage.js` erklærer. Holdes i sync i hånden; afviger de, seeder vi
// en session appen ikke kan læse.
const AUTH_KEYS = ['access_token', 'user_id', 'username', 'account_id', 'account_name'];

const USERS = '/api/v1/users';
const ACCOUNTS = '/api/v1/accounts/';

/**
 * Registrér en frisk bruger og log ind gennem PERIMETEREN.
 *
 * Bemærk afvigelsen fra planen: den foreskrev et selvsigneret HS256-token som
 * `tests/e2e/_env.py`. Vi bruger de rigtige endpoints i stedet, fordi standardkontoen
 * alligevel skabes af en saga vi skal polle efter — så API-vejen er obligatorisk, og et
 * ægte login fjerner dermed JWT_SECRET fra suitens afhængigheder uden at koste et kald.
 */
async function registerAndLogin(api) {
  const suffix = `${Date.now().toString(36)}${Math.floor(Math.random() * 1e6).toString(36)}`;
  const credentials = {
    username: `pw_${suffix}`,
    email: `pw_${suffix}@example.com`,
    password: 'SecurePass123!',
  };

  const registered = await api.post(`${USERS}/register`, { data: credentials });
  if (!registered.ok()) {
    // 429 her betyder rate-limiten, ikke en produktfejl — sig det, så ingen jagter
    // user-service i en halv time.
    throw new Error(
      `register fejlede: ${registered.status()} ${await registered.text()}\n` +
        'Ved 429: perimeterens auth_register-zone er 10r/m burst=5 (nginx.conf:54). ' +
        'Suiten deler én session netop for at holde sig under den — kører der flere ' +
        'workers, eller er suiten kørt gentagne gange inden for et minut?'
    );
  }

  // `username_or_email`, ikke `username` — login og register har IKKE samme feltnavn.
  // Målt: `username` gav 422 `missing: body.username_or_email`. Jf. LoginPage.jsx:11.
  const loggedIn = await api.post(`${USERS}/login`, {
    data: { username_or_email: credentials.username, password: credentials.password },
  });
  if (!loggedIn.ok()) {
    throw new Error(`login fejlede: ${loggedIn.status()} ${await loggedIn.text()}`);
  }

  // { access_token, token_type, user_id, username } — jf. LoginPage.jsx:33
  const body = await loggedIn.json();
  return { credentials, auth: body };
}

/**
 * Poll indtil registrerings-sagaen har skabt standardkontoen.
 *
 * Kontoen er IKKE skabt synkront af /register — den kommer af en event-drevet saga
 * (se tests/e2e/test_full_flow.py). Uden denne ventetid ville fixturen seede en session
 * uden `account_id`, altså præcis den tavse-nuller-tilstand den findes for at forhindre.
 */
async function waitForDefaultAccount(api, token, timeoutMs = 30_000) {
  const deadline = Date.now() + timeoutMs;
  let lastStatus = 'ingen kald nået';

  while (Date.now() < deadline) {
    const resp = await api.get(ACCOUNTS, {
      headers: { Authorization: `Bearer ${token}` },
    });
    lastStatus = `${resp.status()}`;

    if (resp.ok()) {
      const accounts = await resp.json();
      if (Array.isArray(accounts) && accounts.length > 0) {
        const account = accounts.find((a) => a.name === 'Default Account') ?? accounts[0];
        // `idAccount ?? id` er appens egen fallback (AccountSelector.jsx:33), ikke en
        // gætteri: account-service svarer med `idAccount`. Målt — `account.id` alene gav
        // undefined, og fordi seedingen gør `String(...)` blev det strengen "undefined",
        // som er truthy. Derfor er det ID'et der valideres her, ved kilden.
        const accountId = account.idAccount ?? account.id;
        if (accountId === undefined || accountId === null) {
          throw new Error(
            `Kontoen mangler både idAccount og id — svaret er ${JSON.stringify(account)}. ` +
              'Har account-service ændret sit response-schema?'
          );
        }
        return { ...account, resolvedId: accountId };
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }

  throw new Error(
    `Standardkontoen kom ikke inden ${timeoutMs} ms (sidste svar: ${lastStatus}). ` +
      'Sagaen er sandsynligvis ikke gennemført — tjek `docker compose logs ' +
      'account-service-consumer`. Dette er en infrastruktur-fejl, ikke en UI-fejl.'
  );
}

export const test = base.extend({
  /**
   * Worker-scoped session: én bruger, ét token, én konto for hele suiten.
   */
  session: [
    async ({}, use) => {
      const api = await apiRequest.newContext({ baseURL: BASE_URL });
      try {
        const { credentials, auth } = await registerAndLogin(api);
        const account = await waitForDefaultAccount(api, auth.access_token);

        await use({
          api,
          username: credentials.username,
          password: credentials.password,
          token: auth.access_token,
          userId: auth.user_id,
          accountId: account.resolvedId,
          accountName: account.name,
          // Alle fem nøgler, som appen forventer dem i localStorage. `account_id` og
          // `account_name` sættes normalt kun af AccountSelector.jsx:20-25 — vi springer
          // det UI-trin over, men ikke dets bivirkning.
          storage: {
            access_token: auth.access_token,
            user_id: String(auth.user_id),
            username: credentials.username,
            account_id: String(account.resolvedId),
            account_name: account.name,
          },
        });
      } finally {
        await api.dispose();
      }
    },
    { scope: 'worker' },
  ],

  /**
   * En `page` hvor sessionen ER seedet og hvor det er BEVIST at den blev det.
   *
   * `addInitScript` kører før sidens egne scripts på hver navigation, altså før
   * `AuthContext`s `useEffect` læser localStorage — det er hele grunden til at seedingen
   * ikke kan gøres med et `page.evaluate` efter `goto`.
   */
  appPage: async ({ page, session }, use) => {
    await page.addInitScript((storage) => {
      for (const [key, value] of Object.entries(storage)) {
        window.localStorage.setItem(key, value);
      }
    }, session.storage);

    await page.goto('/dashboard');

    // Assertér at seedingen tog. Fixturen må ikke ANTAGE det: en tom eller delvis
    // localStorage giver ikke en fejl, den giver en app der ser tom ud — og en spec der
    // asserterer på "ingen fejl" ville være grøn.
    const seeded = await page.evaluate(
      (keys) => Object.fromEntries(keys.map((k) => [k, window.localStorage.getItem(k)])),
      AUTH_KEYS
    );
    for (const key of AUTH_KEYS) {
      expect(seeded[key], `localStorage.${key} blev ikke seedet`).toBeTruthy();
      // `toBeTruthy()` alene er IKKE nok, og det er målt: da fixturen læste et forkert
      // felt blev `String(undefined)` strengen "undefined" — truthy, seedet, og appen
      // sendte `X-Account-ID: undefined`. Assertionen bestod på præcis den tilstand den
      // findes for at forhindre. Samme fejlmode som resten af dette item handler om.
      expect(
        seeded[key],
        `localStorage.${key} blev seedet med den stringificerede værdi "${seeded[key]}" ` +
          '— et felt er læst forkert et sted opstrøms'
      ).not.toMatch(/^(undefined|null|NaN)$/);
    }

    // Og at appen faktisk anser os for logget ind. Uden dette ville en ændring i
    // AuthContext's bootstrap-krav vise sig som en mystisk assertion-fejl i hver spec
    // i stedet for som én ærlig fejl her.
    await expect(page).toHaveURL(/\/dashboard/);

    await use(page);
  },
});

export { expect };
