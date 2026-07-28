/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    open: true,
    // P3-43: samme perimeter-form som nginx.conf, så `npm run dev` og det byggede
    // image opfører sig ens når serviceUrls.js bliver relativ. Her ER målene
    // browserens host-porte (8004 account, 8007 ai) — ikke container-portene
    // nginx bruger. Holdes i sync med nginx.conf i hånden; rule 5 vogter nginx-siden.
    proxy: Object.fromEntries(
      [
        ['/api/v1/users', 8001],
        ['/api/v1/transactions', 8002],
        ['/api/v1/planned-transactions', 8002],
        ['/api/v1/monthly-budgets', 8003],
        ['/api/v1/budgets', 8003],
        ['/api/v1/accounts', 8004],
        ['/api/v1/account-groups', 8004],
        ['/api/v1/categories', 8005],
        ['/api/v1/subcategories', 8005],
        ['/api/v1/rules', 8005],
        ['/api/v1/goals', 8006],
        ['/api/v1/chat', 8007],
        ['/api/v1/notifications', 8008],
        ['/api/v1/bank', 8009],
        ['/api/v1/graphql', 8010],
        ['/api/v1/sagas', 8010],
      // changeOrigin: FALSE, og det er ikke en detalje. Med `true` omskriver Vite Host til
      // målet (fx localhost:8004), og FastAPI's trailing-slash-redirect bygger sin ABSOLUTTE
      // Location ud fra Host — så GET /api/v1/accounts svarede 307 til
      // http://localhost:8004/api/v1/accounts/, som browseren følger CROSS-ORIGIN. Efter
      // P3-43 trin 3 findes der ingen CORSMiddleware bagved, så symptomet er en CORS-fejl
      // der peger på account-service i stedet for på denne linje. Målt 2026-07-28:
      // Host: localhost:8004 → Location på 8004; Host: localhost:3000 → Location på 3000.
      // Det er samme grund som nginx.conf's `proxy_set_header Host $http_host` — dev-siden
      // havde bare den modsatte indstilling, så de to perimetre ikke opførte sig ens.
      // Alle mål er localhost, så ingen upstream kræver en bestemt Host for at route.
      ].map(([path, port]) => [path, { target: `http://localhost:${port}`, changeOrigin: false }])
    ),
  },
  build: {
    outDir: 'build',
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.js',
    css: true,
    // P2-39: EKSPLICIT include. Uden den bruger vitest sin default-glob
    // (`**/*.{test,spec}.*`) og opsamler Playwright-specs fra `e2e/` — målt:
    // det gjorde `npm test` RØD (36 filer, 1 failed), fordi `@playwright/test`s
    // `test()` ikke kan køre i vitests runner. De to suiter skal ikke bare undgå
    // at overlappe; de må ikke kunne se hinandens filer.
    include: ['src/**/*.{test,spec}.{js,jsx}'],
    // Pin pool explicitly; vitest 3 changes default from 'threads' to 'forks'
    // which alters test timing. Explicit choice = stable across future upgrades.
    pool: 'threads',
  },
});
