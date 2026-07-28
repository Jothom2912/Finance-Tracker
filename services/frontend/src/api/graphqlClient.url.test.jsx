/**
 * P1-16 regressionstest — egen fil, fordi den kun har værdi hvis `graphql-request` IKKE
 * er mocket.
 *
 * Søsterfilen graphqlClient.test.jsx mocker `GraphQLClient` væk for at teste
 * 401-interceptoren. Det er legitimt dér, men det er også præcis grunden til at ingen test
 * fangede at P3-43's relative URL fik biblioteket til at kaste `TypeError: Invalid URL`:
 * den konstruktør der kaster, kørte aldrig. Mocket var blindheden.
 *
 * Derfor bruger denne fil den ægte klient og stubber kun netværket. Det er `fetch`-grænsen
 * der er det rigtige sted at skære: alt over den — URL-konstruktionen, som er det der gik
 * i stykker — er så under test.
 */
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { gqlRequest } from './graphqlClient';

let fetchMock;

beforeEach(() => {
  localStorage.clear();
  fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify({ data: { __typename: 'Query' } }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  );
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('GraphQL-klientens URL (P1-16)', () => {
  it('kalder igennem uden at kaste på URL-konstruktionen', async () => {
    // Selve regressionen: med en relativ URL kastede dette
    // `TypeError: Invalid URL` inde i graphql-request, før fetch blev nået.
    await expect(gqlRequest('{ __typename }')).resolves.toEqual({
      __typename: 'Query',
    });
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it('giver biblioteket en absolut URL på samme origin som dokumentet', async () => {
    await gqlRequest('{ __typename }');

    // graphql-request 7 sender et `URL`-objekt videre til fetch, ikke en streng — netop
    // fordi det selv har kaldt `new URL(...)`. `String()` dækker begge former, så testen
    // ikke brækker på en bibliotek-opgradering der skifter til en streng.
    const url = new URL(String(fetchMock.mock.calls[0][0]));

    // Absolut, fordi graphql-request kræver det (new URL uden base).
    expect(url.protocol).toMatch(/^https?:$/);
    // Samme origin som siden, fordi perimeteren fra ADR-0005 er hele pointen:
    // en absolut URL må ikke snige en fremmed origin ind ad bagvejen.
    expect(url.origin).toBe(window.location.origin);
    expect(url.pathname).toBe('/api/v1/graphql');
  });
});
