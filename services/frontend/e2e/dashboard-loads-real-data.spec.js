// P2-39 test 1 — P1-16-klassen: læsestien fra browseren til read-modellen.
//
// Det er DENNE test der er hele grunden til at instrumentet findes. Gennem hele P1-16 var
// de 346 jsdom-tests og de 24 Python-e2e-tests grønne, mens hver bruger så
// `Fejl: Failed to construct 'URL': Invalid URL` hvor dashboardet skulle være. Ingen af de
// to suiter kunne se det: jsdom'en mocker `GraphQLClient`, og Python-suiten kalder GraphQL
// med httpx og kører altså ikke klienten.
//
// Derfor asserterer denne test på ET BELØB, ikke på at siden mounter. P1-16 gav et MOUNTET
// DOM — med en fejltekst i. `toBeVisible()` på en container ville have været grøn.
//
// VERIFICERET RØD (2026-07-28), og mutationen er valgt efter en fejlslagen kandidat:
//   Kandidat 1 — P1-16 selv genindført (relativ URL i graphqlClient.jsx): rød her, MEN
//     `npm test` blev også rød (2 af 346). P1-16 fik sin egen jsdom-regressionstest da den
//     blev rettet (`graphqlClient.url.test.jsx`), så den linje er dobbeltdækket i dag og
//     kan ikke længere vise at dette instrument er nyt. Planens forventede
//     "346 passed / 1 failed" var skrevet uden det.
//   Kandidat 2 — `X-Account-ID` fjernet fra graphqlClient: GRØN i begge suiter. Gateway'en
//     falder tilbage til brugerens standardkonto ud fra tokenet (gateway auth.py:82-95),
//     så headeren er ikke bærende for en bruger med én konto. Ikke en mutation.
//   Den brugte — `totalIncome` → `totalIncomeTYPO` i `DASHBOARD_QUERY`:
//     **`npm test` 346 passed, denne suite 2 failed.** Det er beviset. GraphQL-dokumentet
//     valideres mod det rigtige schema af INTET andet i repoet, fordi
//     `useDashboardData.test.jsx:6` mocker `../../api/graphqlClient` væk.
import { test, expect } from './fixtures/session.js';

// Tre beløb, valgt så de er utvetydige i sidens tekst og så nettoen er et FJERDE tal
// read-modellen skal have regnet selv. Brugeren er frisk pr. worker, så totalerne
// starter på nul og disse tal er de eneste der findes.
const INCOME = '4242.42';
const EXPENSE = '1337.75';

// Som `formatAmount` (lib/formatters.jsx) skriver dem: da-DK, DKK, to decimaler.
// Vi matcher kun cifrene og separatorerne — ikke valutasymbolet eller mellemrummet før
// det, fordi Intl bruger no-break space dér og ICU-versionen bestemmer hvilken.
const EXPECTED = {
  income: '4.242,42',
  expenses: '1.337,75',
  net: '2.904,67', // 4242.42 - 1337.75 — beregnet af analytics, ikke sendt af os
};

/** Kortet med den givne overskrift, som Playwright-locator. */
function summaryCard(page, heading) {
  return page.locator('.summary-card', { has: page.getByRole('heading', { name: heading }) });
}

async function createTransaction(session, { amount, type, description, date }) {
  const resp = await session.api.post('/api/v1/transactions/', {
    headers: { Authorization: `Bearer ${session.token}` },
    data: {
      account_id: Number(session.accountId),
      account_name: session.accountName,
      amount,
      transaction_type: type,
      description,
      date,
    },
  });
  if (resp.status() !== 201) {
    throw new Error(`transaktion ikke skabt: ${resp.status()} ${await resp.text()}`);
  }
  return resp.json();
}

test('dashboardet viser de faktiske beløb fra read-modellen', async ({
  appPage,
  session,
  pageErrors,
}) => {
  // I dag, fordi dashboardets default-periode er den nuværende budgetmåned. En hardcodet
  // dato ville gøre testen afhængig af hvornår den kører.
  const today = new Date().toISOString().slice(0, 10);

  await createTransaction(session, {
    amount: INCOME,
    type: 'income',
    description: 'P2-39 browser-test indkomst',
    date: today,
  });
  await createTransaction(session, {
    amount: EXPENSE,
    type: 'expense',
    description: 'P2-39 browser-test udgift',
    date: today,
  });

  // Skrivningen er REST mod transaction-service; tallene på dashboardet kommer fra
  // analytics' Elasticsearch-projektion via GraphQL. Der ligger en event imellem, så
  // ventetiden er ægte og hører til systemet — ikke en skjult flake. Vi genindlæser
  // frem for at polle API'et, fordi det er KLIENTEN der er under måling.
  await expect(async () => {
    await appPage.reload();
    await expect(summaryCard(appPage, 'Samlet indkomst')).toContainText(EXPECTED.income);
  }).toPass({ timeout: 60_000, intervals: [1000, 2000, 3000] });

  // De to øvrige kræver ingen ny ventetid: samme svar bar dem alle tre.
  await expect(summaryCard(appPage, 'Samlede udgifter')).toContainText(EXPECTED.expenses);
  await expect(summaryCard(appPage, 'Nettoændring')).toContainText(EXPECTED.net);

  // Og transaktionen skal være nået frem som en RÆKKE, ikke kun som en sum — det er to
  // forskellige felter i det samme GraphQL-svar, og P1-13-klassen af fejl er præcis at
  // det ene halter efter det andet.
  await expect(appPage.getByText('P2-39 browser-test udgift')).toBeVisible();

  // Til sidst: ingen runtime-fejl undervejs. Assertionen står EFTER de andre med vilje —
  // fejler beløbet, vil vi se hvilket beløb der manglede, ikke en konsol-dump.
  expect(pageErrors, `appen skrev fejl til konsollen:\n${pageErrors.join('\n')}`).toEqual([]);
});
