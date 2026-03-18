// cypress/e2e/csv-upload.cy.js

describe('CSV Upload', () => {
  const testUser = {
    email: `csvtest_${Date.now()}@example.com`,
    password: 'TestPassword123'
  };

  beforeEach(() => {
    cy.clearLocalStorage();
    
    // Opret bruger og log ind først
    cy.visit('/register');
    cy.get('[data-cy=username-input]').type(`csvuser_${Date.now()}`);
    cy.get('[data-cy=email-input]').type(testUser.email);
    cy.get('[data-cy=password-input]').type(testUser.password);
    cy.get('[data-cy=password-confirm-input]').type(testUser.password);
    cy.get('[data-cy=register-button]').click();

    // Log ind
    cy.get('[data-cy=email-input]').type(testUser.email);
    cy.get('[data-cy=password-input]').type(testUser.password);
    cy.get('[data-cy=login-button]').click();

    // Vælg eller opret konto
    cy.url().should('include', '/account-selector');
    cy.get('body').then(($body) => {
      if ($body.find('[data-cy=account-button]').length > 0) {
        cy.get('[data-cy=account-button]').first().click();
      } else {
        cy.get('[data-cy=create-account-button]').click();
        cy.get('[data-cy=account-name-input]').type('CSV Test Konto');
        cy.get('[data-cy=create-account-submit-button]').click();
      }
    });

    // Naviger til transaktioner
    cy.visit('/transactions');
    cy.url().should('include', '/transactions');
  });

  it('Uploader CSV fil med transaktioner', () => {
    // Upload CSV fil
    cy.get('[data-cy=csv-upload-input]').selectFile('cypress/fixtures/test-transactions.csv', {
      force: true // Hvis input er hidden
    });

    // Klik upload knap
    cy.get('[data-cy=upload-csv-button]').click();

    // Verificer success besked
    cy.contains('transaktioner importeret', { timeout: 15000 }).should('be.visible');

    // Verificer at transaktioner vises i listen
    cy.get('[data-cy=transaction-list]', { timeout: 10000 }).should('contain', 'Netto');
    cy.get('[data-cy=transaction-list]').should('contain', 'DSB');
    cy.get('[data-cy=transaction-list]').should('contain', 'Netflix');
  });
});

