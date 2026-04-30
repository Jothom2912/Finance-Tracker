/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    open: true,
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
