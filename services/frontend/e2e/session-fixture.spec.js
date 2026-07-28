// P2-39: vagt på instrumentet selv, ikke en måling af appen.
//
// Den findes fordi fixturen har fire kontrakter mod produktkode, som alle kan drifte uden
// at noget fejler højt: `authStorage.js`' fem nøgler, `AuthContext.jsx:17-35`' bootstrap-krav,
// login-payloadens feltnavn (`username_or_email`, ikke `username` — målt som 422) og
// account-svarets `idAccount`. Drifter én af dem, skal ÉN test sige det tydeligt frem for at
// hver spec i suiten fejle på noget der ser ud som en UI-fejl.
import { test, expect } from './fixtures/session.js';

test('fixturen seeder en session appen anser for logget ind', async ({ appPage, session }) => {
  // Ikke bare truthy: en stringificeret `undefined` er truthy og var den faktiske fejl
  // første gang fixturen kørte. Se fixturens egne assertions for samme grund.
  expect(String(session.accountId)).toMatch(/^\d+$/);
  expect(session.token).toBeTruthy();

  // Havde bootstrap-kravene ændret sig, ville vi være redirected til /login.
  await expect(appPage).toHaveURL(/\/dashboard/);

  // Og appen skal FAKTISK have mountet. Uden denne linje var testen grøn under
  // `script-src 'none'`, hvor der ikke kørte en linje JavaScript i browseren: de tre
  // assertions ovenfor kan alle bestå på en tom HTML-side, fordi localStorage seedes af
  // fixturen og URL'en kun ændrer sig hvis React redirecter. Målt som bivirkning af
  // P2-39's kontrol-kørsel — og det er præcis den grøn-på-ingenting-fælde itemet handler om.
  await expect(appPage.getByText('Logget ind som:')).toBeVisible();
  await expect(appPage.getByText(session.username, { exact: true })).toBeVisible();
});
