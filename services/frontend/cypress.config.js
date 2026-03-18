// cypress.config.js
const { defineConfig } = require('cypress');

module.exports = defineConfig({
  e2e: {
    baseUrl: 'http://localhost:3000',
    setupNodeEvents(on, config) {
      // implement node event listeners here
    },
    viewportWidth: 1280,
    viewportHeight: 720,
    video: false,
    screenshotOnRunFailure: true,
    defaultCommandTimeout: 10000,
    requestTimeout: 10000,
    responseTimeout: 10000,
    // Deaktiver server verificering - server skal startes manuelt først
    // Eller brug: npm run start:test (hvis du har en test server script)
  },
  // Deaktiver automatisk server verificering
  watchForFileChanges: false,
});
