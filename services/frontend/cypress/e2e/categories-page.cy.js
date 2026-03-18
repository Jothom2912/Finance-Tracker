// cypress/e2e/categories-page.cy.js

describe('Kategorisiden - Overblik, filtrering og budget-overholdelse', () => {

  function registerAndLogin(prefix) {
    const uniqueId = Date.now();
    const user = {
      username: `${prefix}_${uniqueId}`,
      email: `${prefix}_${uniqueId}@example.com`,
      password: 'TestPassword123',
    };

    cy.visit('/register');
    cy.get('[data-cy=username-input]').type(user.username);
    cy.get('[data-cy=email-input]').type(user.email);
    cy.get('[data-cy=password-input]').type(user.password);
    cy.get('[data-cy=password-confirm-input]').type(user.password);
    cy.get('[data-cy=register-button]').click();

    cy.url().should('include', '/login');

    cy.get('[data-cy=email-input]').type(user.email);
    cy.get('[data-cy=password-input]').type(user.password);
    cy.get('[data-cy=login-button]').click();

    cy.url().should('include', '/account-selector');
    return user;
  }

  function registerLoginAndSelectAccount(prefix) {
    registerAndLogin(prefix);

    cy.intercept('POST', '**/accounts/**').as('createAccountReq');
    cy.get('body').then(($body) => {
      if ($body.find('[data-cy=account-button]').length > 0) {
        cy.window().then((win) => {
          const token = win.localStorage.getItem('access_token');
          cy.request({
            method: 'GET',
            url: 'http://localhost:8000/accounts/',
            headers: { Authorization: `Bearer ${token}` },
          }).then((response) => {
            if (response.body && response.body.length > 0) {
              const id = response.body[0].idAccount || response.body[0].id;
              win.localStorage.setItem('account_id', String(id));
            }
          });
        });
        cy.get('[data-cy=account-button]').first().click();
      } else {
        cy.get('[data-cy=create-account-button]').click();
        cy.get('[data-cy=account-name-input]').type('E2E Test Konto');
        cy.get('[data-cy=create-account-submit-button]').click();

        cy.wait('@createAccountReq').then((interception) => {
          const id = interception.response.body.idAccount || interception.response.body.id;
          if (id) {
            cy.window().then((win) => {
              win.localStorage.setItem('account_id', String(id));
            });
          }
        });
      }
    });

    cy.url().should('include', '/dashboard');
  }

  describe('Uden konto - No-account state', () => {
    beforeEach(() => {
      cy.clearLocalStorage();
    });

    it('Viser "Ingen konto valgt" state når account_id mangler', () => {
      registerLoginAndSelectAccount('noact');

      cy.window().then((win) => {
        win.localStorage.removeItem('account_id');
      });

      cy.visit('/categories');

      cy.get('[data-cy=category-filter-panel]').should('be.visible');
      cy.get('[data-cy=no-account-state]', { timeout: 10000 }).should('be.visible');
      cy.get('[data-cy=no-account-state]').contains('Ingen konto valgt');
      cy.get('[data-cy=no-account-state]').find('a').should('have.attr', 'href', '/account-selector');

      cy.get('.notification--error').should('not.exist');
    });
  });

  describe('Med konto - Fuld funktionalitet', () => {
    beforeEach(() => {
      cy.clearLocalStorage();
      registerLoginAndSelectAccount('catfull');
    });

    it('Viser filterpanel med periode, type og kategori-chips', () => {
      cy.get('[data-cy=nav-categories]').click();
      cy.url().should('include', '/categories');

      cy.get('[data-cy=category-filter-panel]').should('be.visible');
      cy.get('[data-cy=filter-month]').should('be.visible');
      cy.get('[data-cy=filter-year]').should('be.visible');
      cy.get('[data-cy=filter-type]').should('have.value', 'expense');
      cy.get('[data-cy=toggle-all-categories]').should('be.visible');
      cy.get('[data-cy=category-chips]').should('be.visible');
    });

    it('Kategori-chips kan vælges og fravælges', () => {
      cy.get('[data-cy=nav-categories]').click();

      cy.get('[data-cy=category-chips]').find('.category-chip').then(($chips) => {
        if ($chips.length === 0) return;

        const firstChip = $chips.first();
        const chipCy = firstChip.attr('data-cy');

        cy.get(`[data-cy="${chipCy}"]`).click();
        cy.get(`[data-cy="${chipCy}"]`).should('have.class', 'selected');

        cy.get(`[data-cy="${chipCy}"]`).click();
        cy.get(`[data-cy="${chipCy}"]`).should('not.have.class', 'selected');
      });
    });

    it('"Vælg alle" selecterer alle chips, "Fravælg alle" deselecterer', () => {
      cy.get('[data-cy=nav-categories]').click();

      cy.get('[data-cy=category-chips]').find('.category-chip').then(($chips) => {
        if ($chips.length === 0) return;

        cy.get('[data-cy=toggle-all-categories]').click();

        cy.get('[data-cy=category-chips]').find('.category-chip.selected')
          .should('have.length', $chips.length);

        cy.get('[data-cy=toggle-all-categories]').should('contain', 'Fravælg alle');

        cy.get('[data-cy=toggle-all-categories]').click();
        cy.get('[data-cy=category-chips]').find('.category-chip.selected')
          .should('have.length', 0);

        cy.get('[data-cy=toggle-all-categories]').should('contain', 'Vælg alle');
      });
    });

    it('Type-filter skifter mellem udgifter, indtægter og alle', () => {
      cy.get('[data-cy=nav-categories]').click();

      cy.get('[data-cy=category-chips]').find('.category-chip').then(($expenseChips) => {
        const expenseCount = $expenseChips.length;

        cy.get('[data-cy=filter-type]').select('income');
        cy.get('[data-cy=category-chips]').find('.category-chip').then(($incomeChips) => {
          const incomeCount = $incomeChips.length;

          cy.get('[data-cy=filter-type]').select('all');
          cy.get('[data-cy=category-chips]').find('.category-chip')
            .should('have.length', expenseCount + incomeCount);
        });

        cy.get('[data-cy=filter-type]').select('expense');
      });
    });

    it('Periode-ændring opdaterer filter-summary', () => {
      cy.get('[data-cy=nav-categories]').click();

      cy.get('[data-cy=filter-month]').select('06');
      cy.contains('Juni').should('be.visible');

      cy.get('[data-cy=filter-year]').select('2025');
      cy.contains('2025').should('be.visible');
    });

    it('Viser empty state eller spending overview afhængigt af data', () => {
      cy.get('[data-cy=nav-categories]').click();

      cy.get('[data-cy=spending-empty-state], [data-cy=spending-overview]', { timeout: 10000 })
        .should('exist');
    });

    it('"Administrer kategorier" knappen åbner modal', () => {
      cy.get('[data-cy=nav-categories]').click();

      cy.get('[data-cy=manage-categories-btn]').click();

      cy.get('.modal-overlay').should('be.visible');
      cy.get('.modal-content').should('be.visible');
    });
  });

  describe('Med konto og transaktioner - Data visning', () => {
    beforeEach(() => {
      cy.clearLocalStorage();
      registerLoginAndSelectAccount('catdata');

      cy.get('[data-cy=nav-transactions]').click();
      cy.url().should('include', '/transactions');

      cy.intercept('POST', '**/transactions/**').as('createTx');

      cy.get('[data-cy=add-transaction-button]').click();
      cy.get('[data-cy=transaction-form]').should('be.visible');

      cy.get('[data-cy=transaction-category]', { timeout: 10000 })
        .find('option')
        .should('have.length.greaterThan', 1);

      cy.get('[data-cy=transaction-amount]').type('1500');
      cy.get('[data-cy=transaction-description]').type('E2E test udgift');

      cy.get('[data-cy=transaction-category]').then(($select) => {
        const firstVal = $select.find('option').eq(1).val();
        cy.get('[data-cy=transaction-category]').select(firstVal);
      });

      const yesterday = new Date();
      yesterday.setDate(yesterday.getDate() - 1);
      cy.get('[data-cy=transaction-date]').clear().type(yesterday.toISOString().split('T')[0]);
      cy.get('[data-cy=transaction-type-expense]').check();
      cy.get('[data-cy=submit-transaction]').click();

      cy.wait('@createTx').its('response.statusCode').should('eq', 201);
    });

    it('Viser spending overview med data efter transaktion er oprettet', () => {
      cy.get('[data-cy=nav-categories]').click();
      cy.url().should('include', '/categories');

      cy.get('[data-cy=spending-overview], [data-cy=spending-empty-state]', { timeout: 15000 })
        .should('exist');

      cy.get('body').then(($body) => {
        if ($body.find('[data-cy=spending-overview]').length > 0) {
          cy.get('[data-cy=spending-stats]').should('be.visible');
          cy.get('[data-cy=spending-chart]').should('be.visible');
        } else {
          cy.get('[data-cy=spending-empty-state]').should('be.visible');
        }
      });
    });
  });
});
