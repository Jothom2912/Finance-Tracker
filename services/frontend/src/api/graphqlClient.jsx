import { GraphQLClient } from 'graphql-request';
import { handleUnauthorized } from '../utils/handleUnauthorized';
import { GATEWAY_SERVICE_URL } from '../config/serviceUrls';

// P1-16: `graphql-request` kalder `new URL(url)` UDEN base, så en relativ sti kaster
// `TypeError: Invalid URL` før der sendes noget. P3-43 gjorde serviceUrls.js relativ, og
// det brækkede dermed hver GraphQL-læsning i browseren (dashboard, transaktioner,
// kategorier) — usynligt for `curl`, som ikke kører klienten, og for testene i
// graphqlClient.test.jsx, som mocker `GraphQLClient` væk.
//
// Absolutiseringen hører HER og ikke i serviceUrls.js: den er dette biblioteks krav, ikke
// en konfiguration. Alle andre kald går gennem `fetch`, som selv opløser relative URLs mod
// dokumentets base — perimeteren fra ADR-0005 er altså uændret, og URL'en peger stadig på
// samme origin som siden selv.
//
// Beregnes per kald, ikke ved modul-load, så den ikke fastlåses før `window.location`
// findes (jsdom, og et evt. fremtidigt prerender-trin).
function graphqlUrl() {
  return new URL(`${GATEWAY_SERVICE_URL}/graphql`, window.location.origin).toString();
}

function getHeaders() {
  const headers = { 'Content-Type': 'application/json' };
  const token = localStorage.getItem('access_token');
  const accountId = localStorage.getItem('account_id');

  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (accountId) headers['X-Account-ID'] = accountId;

  return headers;
}

export function getGraphQLClient() {
  return new GraphQLClient(graphqlUrl(), { headers: getHeaders() });
}

export async function gqlRequest(query, variables = {}) {
  const client = getGraphQLClient();
  try {
    return await client.request(query, variables);
  } catch (error) {
    if (error.response?.status === 401) {
      handleUnauthorized();
      return new Promise(() => {});
    }
    throw error;
  }
}
