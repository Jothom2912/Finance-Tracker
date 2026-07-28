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
      ].map(([path, port]) => [path, { target: `http://localhost:${port}`, changeOrigin: true }])
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
    // Pin pool explicitly; vitest 3 changes default from 'threads' to 'forks'
    // which alters test timing. Explicit choice = stable across future upgrades.
    pool: 'threads',
  },
});
