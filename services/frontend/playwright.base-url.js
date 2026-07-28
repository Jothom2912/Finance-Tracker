// Ét sted for perimeterens adresse, fordi både playwright.config.js og de worker-scopede
// fixtures har brug for den — og en fixture kan ikke læse det test-scopede `baseURL`-option.
//
// LIGGER BEVIDST UDEN FOR `testDir`. Alt hvad playwright.config.js importerer bliver
// indlæst i config-konteksten, og en fil dér må ikke være en del af test-træet: da denne
// konstant lå i `e2e/fixtures/`, fejlede hele suiten med "Playwright Test did not expect
// test() to be called here" og `No tests found`. Målt, ikke formodet.
//
// 127.0.0.1, IKKE localhost: P3-43's første perimeter-måling ramte en Vite dev-server på
// [::1]:3000 i stedet for nginx-containeren og fik plausible svar fra den forkerte komponent.
// Denne suite måler det BYGGEDE image bag perimeteren (CSP + rate limits), så adressen skal
// være utvetydig.
export const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? 'http://127.0.0.1:3000';
