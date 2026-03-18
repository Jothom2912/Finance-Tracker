// ***********************************************
// This example commands.js shows you how to
// create various custom commands and overwrite
// existing commands.
//
// For more comprehensive examples of custom
// commands please read more here:
// https://on.cypress.io/custom-commands
// ***********************************************

/**
 * Custom command to login a user
 * @param {string} email - User email or username
 * @param {string} password - User password
 */
Cypress.Commands.add('login', (email, password) => {
  cy.visit('/login');
  cy.get('[data-cy=email-input]').type(email);
  cy.get('[data-cy=password-input]').type(password);
  cy.get('[data-cy=login-button]').click();
  // Wait for redirect to account selector or dashboard
  cy.url().should('not.include', '/login');
});

/**
 * Custom command to register a new user
 * @param {object} userData - User data object with username, email, password
 */
Cypress.Commands.add('register', (userData) => {
  cy.visit('/register');
  cy.get('[data-cy=username-input]').type(userData.username);
  cy.get('[data-cy=email-input]').type(userData.email);
  cy.get('[data-cy=password-input]').type(userData.password);
  cy.get('[data-cy=password-confirm-input]').type(userData.password);
  cy.get('[data-cy=register-button]').click();
});

/**
 * Custom command to select or create an account
 * @param {string} accountName - Optional account name to create
 */
Cypress.Commands.add('selectOrCreateAccount', (accountName = 'Test Account') => {
  cy.url().should('include', '/account-selector');
  
  // Check if account list exists
  cy.get('body').then(($body) => {
    if ($body.find('[data-cy=account-list]').length > 0) {
      // Account exists, click first one
      cy.get('[data-cy=account-button]').first().click();
    } else {
      // No accounts, create one
      cy.get('[data-cy=create-account-button]').click();
      cy.get('[data-cy=account-name-input]').type(accountName);
      cy.get('[data-cy=create-account-submit-button]').click();
    }
  });
  
  // Wait for redirect to dashboard
  cy.url().should('include', '/dashboard');
});
