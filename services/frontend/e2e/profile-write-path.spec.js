// F2-08: user-services første skrive-sti til en eksisterende bruger, drevet gennem
// perimeteren i en rigtig browser.
//
// EGEN BRUGER, IKKE DEN DELTE `session`-FIXTURE. Fixturen er worker-scoped og deler én
// bruger med hele suiten (se fixtures/session.js). Denne spec ændrer brugerens password og
// brugernavn — gjorde den det på den delte session, ville hver EFTERFØLGENDE spec fejle på
// login med en fejl der ikke ligner sin årsag.
//
// ÉN test og ikke tre, selvom der er tre ting at vise. Grunden er perimeterens
// register-zone: 10r/m burst=5 (nginx.conf:53-54). Suiten har præcis ét delt
// registreringsbudget, og en test-scoped fixture ville koste en registrering PER test.
// Sekvensen herunder er i øvrigt også den rigtige rækkefølge at måle i — password-skiftet
// skal være sidst, fordi det ugyldiggør de credentials de foregående trin bruger.
//
// De tre ting den beviser, som ingen backend-test kan:
//   1. Navigationen viser det nye brugernavn UDEN reload — AuthContext.updateUser gjort
//      observerbart. Uden det kommer navnet fra login-svarets localStorage-kopi og bliver
//      stående til re-login.
//   2. Et forkert `current_password` afviser UDEN at logge brugeren ud. Det er
//      403-vs-401-fælden set fra brugerens side: en 401 ville få apiClient til at rydde
//      sessionen og redirecte til /login.
//   3. Password-skiftet holder over et rigtigt log ud / log ind gennem UI'et.
import { test as base, request as apiRequest, expect } from '@playwright/test';

import { BASE_URL } from '../playwright.base-url.js';
import { registerAndLogin, waitForDefaultAccount } from './fixtures/session.js';

const test = base.extend({
  /** Engangs-session med egen bruger. Worker-scoped: én registrering per kørsel. */
  ownSession: [
    async ({}, use) => {
      const api = await apiRequest.newContext({ baseURL: BASE_URL });
      try {
        const { credentials, auth } = await registerAndLogin(api);
        const account = await waitForDefaultAccount(api, auth.access_token);
        await use({
          credentials,
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
});

test('profil: brugernavn og adgangskode kan ændres end-to-end', async ({ page, ownSession }) => {
  const { username, password } = ownSession.credentials;
  const nytNavn = `${username}_ny`;
  const nytPassword = 'HeltNytPass456!';

  // Seed FØR sidens scripts: AuthContext læser localStorage i sin useEffect, så et
  // page.evaluate efter goto ville komme for sent.
  await page.addInitScript((entries) => {
    for (const [key, value] of Object.entries(entries)) {
      window.localStorage.setItem(key, value);
    }
  }, ownSession.storage);

  await page.goto('/profile');

  // Bevis at vi er inde og at siden mountede — ikke en redirect til /login, ikke en tom
  // HTML-side. Uden dette ville en seeding-fejl vise sig som en produktfejl nedenfor.
  await expect(page).toHaveURL(/\/profile/);
  await expect(page.getByTestId('profile-username-input')).toBeVisible();
  await expect(page.getByTestId('user-menu-username')).toHaveText(username);

  // ── 1. Brugernavn: slår igennem i navigationen uden reload ────────
  await page.getByTestId('profile-username-input').fill(nytNavn);
  await page.getByTestId('profile-username-submit').click();

  // Ingen reload imellem. Det er hele pointen: krævede assertionen et page.reload() for at
  // bestå, ville den måle localStorage-kopien igen frem for updateUser.
  await expect(page.getByTestId('user-menu-username')).toHaveText(nytNavn);

  // Og skiftet er persisteret, ikke kun lokal state. Beviset tages fra SERVEREN:
  // profilfeltet fyldes af `fetchMe()`, mens navigationen efter en reload læser
  // localStorage — som `addInitScript` re-seeder ved HVER navigation med det oprindelige
  // navn. En assertion på navigationen her ville altså måle fixturen og ikke appen; målt,
  // den var rød på præcis det.
  await page.reload();
  await expect(page.getByTestId('profile-username-input')).toHaveValue(nytNavn);

  // ── 2. Forkert nuværende password afviser uden udlogning ──────────
  await page.getByTestId('profile-current-password').fill('helt_forkert_password');
  await page.getByTestId('profile-new-password').fill(nytPassword);
  await page.getByTestId('profile-confirm-password').fill(nytPassword);
  await page.getByTestId('profile-password-submit').click();

  // Brugeren skal SE en fejl. "Ikke logget ud" alene ville også være sandt hvis knappen
  // ikke gjorde noget — det positive udfald er at afvisningen når frem som en besked.
  const fejlToast = page.getByTestId('notification-assertive').locator('.notification--error');
  await expect(fejlToast).toBeVisible();

  // Var svaret en 401, stod vi nu på /login med tom localStorage — en udlogning som straf
  // for en tastefejl. 403 rører ikke sessionen.
  await expect(page.getByTestId('user-menu-trigger')).toBeVisible();
  await expect(page).toHaveURL(/\/profile/);
  expect(await page.evaluate(() => window.localStorage.getItem('access_token'))).toBeTruthy();

  // Fejl-toasts auto-lukker IKKE (NotificationContext: kun success får en timer), og
  // containeren ligger over navigationens højre hjørne. Uden dette opsnapper den kliksene
  // på brugermenuen nedenfor.
  await fejlToast.getByRole('button', { name: 'Luk besked' }).click();
  await expect(fejlToast).toHaveCount(0);

  // ── 3. Rigtigt password: skift, log ud, log ind med det nye ───────
  await page.getByTestId('profile-current-password').fill(password);
  await page.getByTestId('profile-new-password').fill(nytPassword);
  await page.getByTestId('profile-confirm-password').fill(nytPassword);
  await page.getByTestId('profile-password-submit').click();

  // Feltet ryddes først når kaldet lykkedes — det er signalet om at skiftet gik igennem,
  // og det gør ventetiden nedenfor til andet end en gætning på timing.
  await expect(page.getByTestId('profile-current-password')).toHaveValue('');

  await page.getByTestId('user-menu-trigger').click();
  await page.getByTestId('user-menu-logout').click();
  await expect(page).toHaveURL(/\/login/);

  // Log ind med BEGGE de nye værdier: nyt brugernavn og nyt password. Består dette, er
  // begge skrivninger nået hele vejen til databasen.
  await page.locator('#username_or_email').fill(nytNavn);
  await page.locator('#password').fill(nytPassword);
  await page.getByRole('button', { name: 'Log ind' }).click();

  // LoginPage navigerer til /account-selector ved succes. Var passwordet afvist, blev vi
  // stående på /login med en fejlbesked.
  await expect(page).toHaveURL(/\/account-selector/);
});
