// P2-40 test 4 — instrumentet der kan se konto-scoping.
//
// Hullet den lukker: `session`-fixturen seeder ÉN konto pr. bruger, og med én konto er
// enhver server-side konto-fallback usynlig. P2-39 forsøgte at bruge netop det som
// mutations-kontrol — `X-Account-ID` fjernet fra graphqlClient.jsx, image genbygget — og
// ALLE suiter blev grønne. Konklusionen dengang var at headeren "ikke var bærende"; den
// rigtige konklusion var at instrumentet ikke kunne måle den. Denne spec kan.
//
// Konstruktionen: brugeren har to konti, og den VALGTE er den anden — ikke standardkontoen.
// Det er bevidst og bærende. Var standardkontoen den valgte, ville en server der ignorerer
// `X-Account-ID` og falder tilbage til standardkontoen svare rigtigt ved et tilfælde, og
// kontrollen ville være grøn igen. Nu er de to konti utvetydigt forskellige svar, uanset
// hvilken fallback-regel serveren har.
//
// Assertionen er tosidet med vilje: den valgte kontos beløb SKAL vises, og den anden kontos
// SKAL IKKE. Kun den positive halvdel ville være grøn på et dashboard der viste summen af
// alle konti; kun den negative ville være grøn på et tomt dashboard.
//
// VERIFICERET RØD (2026-07-29) med præcis P2-39's mutation: `X-Account-ID` fjernet fra
// graphqlClient.jsx, frontend-imaget genbygget. Resultatet:
//   denne spec 1 failed — `Samlede udgifter` viste "10.449,74 kr.", altså STANDARDKONTOENS
//     total, hvor den valgte kontos 2.718,28 skulle stå.
//   de tre øvrige browser-specs: grønne.
//   `npm test`: 346 passed.
// Det sidste er hele pointen: jsdom-laget kan strukturelt ikke se dette, fordi
// `graphqlClient` er mocket væk dér.
import { test, expect } from './fixtures/session.js';

// Beløb der ikke findes andre steder i suiten, og som ikke er hinandens delstrenge.
const SELECTED_EXPENSE = '2718.28';
const OTHER_EXPENSE = '9111.99';

// Som `formatAmount` (lib/formatters.jsx) skriver dem: da-DK, to decimaler. Kun cifre og
// separatorer — ikke valutasymbolet, hvis foranstillede mellemrum er et no-break space hvis
// bredde ICU-versionen bestemmer.
const SHOWN = { selected: '2.718,28', other: '9.111,99' };

const SELECTED_DESC = 'P2-40 valgt konto';
const OTHER_DESC = 'P2-40 anden konto';

/** Kortet med den givne overskrift, som Playwright-locator. */
function summaryCard(page, heading) {
  return page.locator('.summary-card', { has: page.getByRole('heading', { name: heading }) });
}

async function createTransaction(session, { accountId, accountName, amount, description, date }) {
  const resp = await session.api.post('/api/v1/transactions/', {
    headers: { Authorization: `Bearer ${session.token}` },
    data: {
      account_id: Number(accountId),
      account_name: accountName,
      amount,
      transaction_type: 'expense',
      description,
      date,
    },
  });
  if (resp.status() !== 201) {
    throw new Error(`transaktion ikke skabt: ${resp.status()} ${await resp.text()}`);
  }
  return resp.json();
}

/**
 * Læs den ANDEN kontos udgiftstotal fra read-modellen, med den anden kontos header.
 */
async function readOtherAccountExpenses(session, { month, year }) {
  const query = `{ periodOverview(month: ${month}, year: ${year}) { totalExpenses } }`;
  const resp = await session.api.post('/api/v1/graphql', {
    headers: {
      Authorization: `Bearer ${session.token}`,
      'X-Account-ID': String(session.defaultAccountId),
    },
    data: { query },
  });
  expect(resp.status(), await resp.text()).toBe(200);
  const body = await resp.json();
  expect(body.errors, JSON.stringify(body.errors)).toBeUndefined();
  return Number(body.data.periodOverview.totalExpenses);
}

/**
 * Vent til read-modellen har MODTAGET den anden kontos nye beløb, målt som en DELTA.
 *
 * Uden dette trin er den negative assertion nedenfor værdiløs: "beløbet vises ikke" er
 * trivielt sandt så længe eventet blot ikke er nået frem endnu. Vi beviser altså at tallet ER
 * i læsesiden, og derefter at det ALLIGEVEL ikke vises på den valgte kontos dashboard. Det er
 * forskellen mellem at måle scoping og at måle latency.
 *
 * En DELTA og ikke en eksakt total, fordi standardkontoen deles med
 * `dashboard-loads-real-data.spec.js` — samme worker, samme bruger, samme konto. Første
 * udgave asserterede `totalExpenses == 9111.99` og fik 10449.74, altså vores beløb plus den
 * anden specs 1337.75. Prædikatet var forkert, ikke produktet. En delta gør testen uafhængig
 * af hvad der ellers ligger på kontoen, og er stadig eksakt (workers: 1, fullyParallel: false,
 * så ingen anden spec skriver imens).
 */
async function waitForOtherAccountDelta(session, period, before) {
  await expect(async () => {
    const now = await readOtherAccountExpenses(session, period);
    expect(now - before).toBeCloseTo(Number(OTHER_EXPENSE), 2);
  }).toPass({ timeout: 60_000, intervals: [1000, 2000, 3000] });
}

test('dashboardet viser den VALGTE kontos tal, ikke den anden kontos', async ({
  accountScopedPage,
  twoAccountSession,
  pageErrors,
}) => {
  const session = twoAccountSession;
  // I dag, fordi dashboardets default-periode er den nuværende budgetmåned.
  const today = new Date();
  const isoDate = today.toISOString().slice(0, 10);
  const period = { month: today.getMonth() + 1, year: today.getFullYear() };

  // Baseline FØR skrivningen: standardkontoen kan allerede have data fra en anden spec.
  const otherBefore = await readOtherAccountExpenses(session, period);

  await createTransaction(session, {
    accountId: session.defaultAccountId,
    accountName: session.defaultAccountName,
    amount: OTHER_EXPENSE,
    description: OTHER_DESC,
    date: isoDate,
  });
  await createTransaction(session, {
    accountId: session.accountId,
    accountName: session.accountName,
    amount: SELECTED_EXPENSE,
    description: SELECTED_DESC,
    date: isoDate,
  });

  await waitForOtherAccountDelta(session, period, otherBefore);

  // Skrivningen er REST mod transaction-service; tallene kommer fra analytics'
  // Elasticsearch-projektion via GraphQL. Vi genindlæser frem for at polle API'et, fordi det
  // er KLIENTEN der er under måling.
  await expect(async () => {
    await accountScopedPage.reload();
    await expect(summaryCard(accountScopedPage, 'Samlede udgifter')).toContainText(SHOWN.selected);
  }).toPass({ timeout: 60_000, intervals: [1000, 2000, 3000] });

  // Den negative halvdel. `body`-locatoren, ikke kortet: beløbet må ikke stå NOGET sted på
  // siden — heller ikke i transaktionslisten eller i en graf-tooltip.
  await expect(accountScopedPage.locator('body')).not.toContainText(SHOWN.other);
  await expect(accountScopedPage.getByText(SELECTED_DESC)).toBeVisible();
  await expect(accountScopedPage.getByText(OTHER_DESC)).toHaveCount(0);

  expect(pageErrors, `appen skrev fejl til konsollen:\n${pageErrors.join('\n')}`).toEqual([]);
});
