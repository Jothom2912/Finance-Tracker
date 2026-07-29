// P2-39: fixturen der ejer session-seedingen.
//
// Den findes fordi seedingen har en fælde der ikke fejler. `authStorage.js:1` erklærer FEM
// nøgler, men `AuthContext.jsx:17-35` kræver kun tre af dem for at anse brugeren for logget
// ind. Uden `account_id` sender `apiClient` ingen `X-Account-ID` (apiClient.jsx:13-14), og
// REST-læsningerne svarer med **tavse nuller i stedet for en fejl** — altså en test der ser
// grøn ud på en tom app. Målt under P3-25. Den slags må ikke ligge i hver spec.
//
// PRÆCISERING (målt i P2-39's kontrol-kørsel): på GRAPHQL-stien er headeren ikke bærende
// for `session`. Gateway'en falder tilbage til brugerens standardkonto ud fra tokenet
// (gateway auth.py:82-95), så fjerner man `X-Account-ID` fra graphqlClient, bliver enhver
// spec der kun bruger `session` grøn — den har én konto pr. bruger, og med én konto er
// enhver fallback det rigtige svar.
//
// LUKKET I P2-40: `twoAccountSession` + `accountScopedPage` nedenfor seeder to konti og
// vælger den ANDEN, og `dashboard-scopes-to-selected-account.spec.js` er rød på netop den
// mutation. Konto-scoping er altså målt nu — men kun af den spec. En grøn `appPage`-spec
// siger stadig intet om den.
//
// Fixturen er worker-scoped: hele suiten deler én bruger og én session. Det er ikke en
// optimering, det er perimeteren — nginx rate-limiter /users/login og /users/register til
// 10r/m med burst=5 (nginx.conf:53-54, P2-27), så en per-test-registrering ville gøre 429
// til en flake-kilde der ligner en produktfejl.
//
// BUDGETTET ER DELT (F2-08). `registerAndLogin` og `waitForDefaultAccount` er eksporteret,
// fordi `profile-write-path.spec.js` MÅ have sin egen bruger: den ændrer password og
// brugernavn, og gjorde den det på den delte session, ville hver efterfølgende spec fejle på
// login — altså langt fra sin årsag. Prisen er én ekstra registrering per kørsel, og der er
// plads under burst=5. Men pladsen er ENDELIG: tilføjer du endnu en engangsbruger, så tæl
// hvor mange der er i alt først. En 429 herfra ligner en produktfejl.
import { test as base, request as apiRequest, expect } from '@playwright/test';

import { BASE_URL } from '../../playwright.base-url.js';

// Præcis de nøgler `authStorage.js` erklærer. Holdes i sync i hånden; afviger de, seeder vi
// en session appen ikke kan læse.
const AUTH_KEYS = ['access_token', 'user_id', 'username', 'account_id', 'account_name'];

const USERS = '/api/v1/users';
const ACCOUNTS = '/api/v1/accounts/';

/** Statuskode-specifik diagnose for en fejlet registrering. */
function diagnoseRegisterFailure(status) {
  if (status === 429) {
    return (
      'perimeterens auth_register-zone er 10r/m burst=5 (nginx.conf:54). Suiten deler én ' +
      'session netop for at holde sig under den — kører der flere workers, eller er suiten ' +
      'kørt gentagne gange inden for et minut?'
    );
  }
  if (status === 502) {
    return (
      'nginx nåede ikke user-service — næsten helt sikkert **P3-45**: nginx opløser ' +
      "upstream-navne ved config-load og cacher IP'en, så et `docker compose up --build " +
      '<service>` der genskaber user-service med en ny IP giver 502 indtil ' +
      '`docker compose restart frontend`. Ramte P2-40, hvor rate-limit-hintet dengang stod ' +
      'ubetinget og fik en 502 til at læse som en 429. ' +
      'Bekræft med `docker logs finance-tracker-frontend-1` → "connect() failed".'
    );
  }
  return 'ikke en kendt perimeter-fejl — læs svaret ovenfor og user-services logs.';
}

/**
 * Registrér en frisk bruger og log ind gennem PERIMETEREN.
 *
 * Bemærk afvigelsen fra planen: den foreskrev et selvsigneret HS256-token som
 * `tests/e2e/_env.py`. Vi bruger de rigtige endpoints i stedet, fordi standardkontoen
 * alligevel skabes af en saga vi skal polle efter — så API-vejen er obligatorisk, og et
 * ægte login fjerner dermed JWT_SECRET fra suitens afhængigheder uden at koste et kald.
 */
export async function registerAndLogin(api) {
  const suffix = `${Date.now().toString(36)}${Math.floor(Math.random() * 1e6).toString(36)}`;
  const credentials = {
    username: `pw_${suffix}`,
    email: `pw_${suffix}@example.com`,
    password: 'SecurePass123!',
  };

  const registered = await api.post(`${USERS}/register`, { data: credentials });
  if (!registered.ok()) {
    // Hintet er BETINGET af status'en. Da rate-limit-forklaringen stod ubetinget, læste en
    // 502 som en 429, og diagnosen gik efter nginx.conf's zoner i stedet for efter det der
    // faktisk var i vejen — målt i P2-40. En fejlbesked der gætter koster mere end en der
    // kun oplyser status.
    throw new Error(
      `register fejlede: ${registered.status()} ${await registered.text()}\n` +
        diagnoseRegisterFailure(registered.status())
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
export async function waitForDefaultAccount(api, token, timeoutMs = 30_000) {
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
        // KUN navnet, ingen `?? accounts[0]`-hale (P2-40). Halen så defensiv ud, men den var
        // den samme fejl gateway'en havde: findes 'Default Account' ikke, er `accounts[0]`
        // ikke et dårligere svar — det er et svar om en ANDEN konto, og suiten ville måle
        // den forkerte. Regelen er ét navn og et partielt unique index
        // (`one_default_per_user`, migration 002); findes kontoen ikke, er det en fejl i
        // seedingen og skal siges.
        const account = accounts.find((a) => a.name === 'Default Account');
        if (!account) {
          throw new Error(
            "Ingen konto hedder 'Default Account' — svaret er " +
              `${JSON.stringify(accounts.map((a) => a.name))}. Har ` +
              'account_creation_consumer ændret navnet? Vi vælger IKKE bare den første ' +
              'konto: det er præcis fejlen P2-40 rettede i gateway auth.py.'
          );
        }
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

/**
 * Opret en EKSTRA konto på den allerede registrerede bruger.
 *
 * Ingen ny bruger: registrerings-perimeteren er 10r/m burst=5 (nginx.conf:54), og to konti
 * på ÉT token er i øvrigt præcis den tilstand vi vil måle.
 */
async function createSecondAccount(api, token, name) {
  const resp = await api.post(ACCOUNTS, {
    headers: { Authorization: `Bearer ${token}` },
    data: { name, saldo: 0, budget_start_day: 1 },
  });
  if (resp.status() !== 201) {
    throw new Error(`kunne ikke oprette '${name}': ${resp.status()} ${await resp.text()}`);
  }
  const account = await resp.json();
  const accountId = account.idAccount ?? account.id;
  if (accountId === undefined || accountId === null) {
    throw new Error(`Den nye konto mangler både idAccount og id: ${JSON.stringify(account)}`);
  }
  return { ...account, resolvedId: accountId };
}

/**
 * Seed localStorage FØR sidens scripts, åbn dashboardet, og BEVIS at seedingen tog.
 *
 * Delt mellem `appPage` og `accountScopedPage`, fordi beviset er det der gør fixturen andet
 * end en antagelse — og en kopi af det ville før eller siden være den halve.
 *
 * `addInitScript` kører før sidens egne scripts på hver navigation, altså før `AuthContext`s
 * `useEffect` læser localStorage — det er hele grunden til at seedingen ikke kan gøres med
 * et `page.evaluate` efter `goto`.
 */
async function seedAndOpenDashboard(page, storage) {
  await page.addInitScript((entries) => {
    for (const [key, value] of Object.entries(entries)) {
      window.localStorage.setItem(key, value);
    }
  }, storage);

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
    // `toBeTruthy()` alene er IKKE nok, og det er målt: da fixturen læste et forkert felt
    // blev `String(undefined)` strengen "undefined" — truthy, seedet, og appen sendte
    // `X-Account-ID: undefined`. Assertionen bestod på præcis den tilstand den findes for
    // at forhindre. Samme fejlmode som resten af dette item handler om.
    expect(
      seeded[key],
      `localStorage.${key} blev seedet med den stringificerede værdi "${seeded[key]}" ` +
        '— et felt er læst forkert et sted opstrøms'
    ).not.toMatch(/^(undefined|null|NaN)$/);
  }

  // Og at appen faktisk anser os for logget ind. Uden dette ville en ændring i
  // AuthContext's bootstrap-krav vise sig som en mystisk assertion-fejl i hver spec i
  // stedet for som én ærlig fejl her.
  await expect(page).toHaveURL(/\/dashboard/);
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
   * Alt appen har skrevet til konsollen, og alle ubehandlede exceptions.
   *
   * Dette er det signal de 346 jsdom-tests ikke har: P1-16's
   * `TypeError: Failed to construct 'URL'` var en runtime-fejl i klienten, og den
   * eneste grund til at nogen opdagede den var at et menneske åbnede konsollen.
   *
   * Egen fixture, ikke to `page.on(...)` i hver spec, fordi lytterne skal hænge på FØR
   * `appPage`s `goto`. Playwright sætter fixtures op i den rækkefølge de er afhængige af
   * hinanden, så `appPage`'s afhængighed nedenfor er det der garanterer rækkefølgen —
   * lytter man i test-kroppen, er den første sideindlæsning allerede sket.
   */
  pageErrors: async ({ page }, use) => {
    const errors = [];
    page.on('pageerror', (err) => errors.push(`pageerror: ${err.message}`));

    // 5xx fanges på RESPONSE-grænsen, ikke kun i konsollen. Browseren logger selv
    // "Failed to load resource: the server responded with a status of 500" — men UDEN
    // URL'en, og præcis den besked var alt CI gav ved første røde kørsel. Det kostede en
    // lokal reproduktion at finde ud af hvilken service det var. Nu står endpointet i
    // fejlbeskeden.
    page.on('response', (resp) => {
      if (resp.status() >= 500) {
        errors.push(`http ${resp.status()}: ${resp.request().method()} ${resp.url()}`);
      }
    });

    page.on('console', (msg) => {
      if (msg.type() !== 'error') return;
      // Drop browserens egen URL-løse variant af det response-lytteren ovenfor allerede
      // har fanget med adresse på. Ellers rapporteres hver 5xx to gange, og den ene
      // halvdel er den ubrugelige.
      if (/Failed to load resource/.test(msg.text())) return;
      errors.push(`console.error: ${msg.text()}`);
    });

    await use(errors);
  },

  /**
   * En `page` hvor sessionen ER seedet og hvor det er BEVIST at den blev det.
   */
  appPage: async ({ page, pageErrors, session }, use) => {
    // `pageErrors` bruges ikke her; afhængigheden ER virkningen (lytterne hænger på før
    // `goto` i helperen). Fjernes den, holder specs op med at se fejl fra første load.
    void pageErrors;

    await seedAndOpenDashboard(page, session.storage);
    await use(page);
  },

  /**
   * Worker-scoped session med TO konti, hvor den ANDEN er den valgte (P2-40).
   *
   * Findes fordi `session` seeder én konto pr. bruger, og med én konto er enhver
   * server-side konto-fallback usynlig: P2-39 fjernede `X-Account-ID` fra graphqlClient som
   * mutations-kontrol og fik ALLE suiter grønne. Instrumentet kunne ikke se konto-scoping —
   * det var ikke en egenskab ved produktet, men ved fixturen.
   *
   * At den valgte konto er den ANDEN, og ikke standardkontoen, er det bærende valg. Var
   * standardkontoen den valgte, ville en server der ignorerer `X-Account-ID` og falder
   * tilbage til standardkontoen svare rigtigt ved et tilfælde, og kontrollen ville være
   * grøn igen.
   */
  twoAccountSession: [
    async ({ session }, use) => {
      const second = await createSecondAccount(session.api, session.token, 'P2-40 Anden Konto');

      await use({
        ...session,
        // Den VALGTE konto for denne session er den anden.
        accountId: second.resolvedId,
        accountName: second.name,
        // Standardkontoen beholdes navngivet, så specs kan lægge data på den og assertere
        // at de IKKE vises.
        defaultAccountId: session.accountId,
        defaultAccountName: session.accountName,
        storage: {
          ...session.storage,
          account_id: String(second.resolvedId),
          account_name: second.name,
        },
      });
    },
    { scope: 'worker' },
  ],

  /**
   * Som `appPage`, men med tokonto-sessionen — altså den anden konto valgt.
   */
  accountScopedPage: async ({ page, pageErrors, twoAccountSession }, use) => {
    void pageErrors;

    await seedAndOpenDashboard(page, twoAccountSession.storage);
    await use(page);
  },
});

export { expect };
