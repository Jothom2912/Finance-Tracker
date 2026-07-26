// Fælles sidestørrelse for transaktionslisten OG søgningen. De to læsestier
// fylder én pager, så "side 2" skal dække samme rækkeinterval i begge tilstande
// — ellers skifter pagerens tekst mellem "Viser 1–50 af 93" og "Viser 1–100 af
// 400" i samme widget. 50 var i forvejen REST-defaulten og gateway-resolverens
// default; søgningen (der hardcoder 100) er den der bringes i tråd.
// Jf. decisions/2026-07-26-transaction-list-envelope.md.
export const PAGE_SIZE = 50;

/**
 * Antal sider for et totalantal rækker.
 *
 * Bunder i 1: en tom periode har stadig én (tom) side, så en clamp mod
 * pageCount aldrig kan sætte sidetallet til 0.
 *
 * @param {number|null|undefined} totalCount
 * @param {number} pageSize
 * @returns {number} >= 1
 */
export function pageCountOf(totalCount, pageSize = PAGE_SIZE) {
  if (!Number.isFinite(totalCount) || totalCount <= 0) return 1;
  return Math.max(1, Math.ceil(totalCount / pageSize));
}
