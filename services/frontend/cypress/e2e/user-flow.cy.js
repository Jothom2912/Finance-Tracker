// cypress/e2e/user-flow.cy.js

describe('User Flow - Opret bruger til transaktion', () => {
  // Generer unik email for hver test-kørsel
  const testUser = {
    username: `testuser_${Date.now()}`,
    email: `test_${Date.now()}@example.com`,
    password: 'TestPassword123'
  };

  beforeEach(() => {
    // Clear localStorage før hver test
    cy.clearLocalStorage();
  });

  it('Komplet bruger flow: opret → login → account selector → dashboard → transaktion', () => {
    // ===== STEP 1: Opret bruger =====
    cy.visit('/register');

    cy.get('[data-cy=username-input]').type(testUser.username);
    cy.get('[data-cy=email-input]').type(testUser.email);
    cy.get('[data-cy=password-input]').type(testUser.password);
    cy.get('[data-cy=password-confirm-input]').type(testUser.password);
    cy.get('[data-cy=register-button]').click();

    // Verificer redirect til login
    cy.url().should('include', '/login');
    cy.contains('Log ind').should('be.visible');

    // ===== STEP 2: Log ind =====
    cy.get('[data-cy=email-input]').type(testUser.email);
    cy.get('[data-cy=password-input]').type(testUser.password);
    cy.get('[data-cy=login-button]').click();

    // Verificer redirect til account selector
    cy.url().should('include', '/account-selector');

    // ===== STEP 3: Vælg eller opret konto =====
    // Intercept account requests
    cy.intercept('POST', '**/accounts/**').as('createAccount');
    cy.intercept('GET', '**/accounts/**').as('getAccounts');
    
    cy.get('body').then(($body) => {
      if ($body.find('[data-cy=account-button]').length > 0) {
        // Account eksisterer - hent account_id fra API før vi klikker
        cy.window().then((win) => {
          const token = win.localStorage.getItem('access_token');
          cy.request({
            method: 'GET',
            url: 'http://localhost:8000/accounts/',
            headers: {
              'Authorization': `Bearer ${token}`
            }
          }).then((response) => {
            if (response.body && response.body.length > 0) {
              const firstAccountId = response.body[0].idAccount || response.body[0].id;
              win.localStorage.setItem('account_id', String(firstAccountId));
              cy.log('✅ Sat account_id fra eksisterende account:', firstAccountId);
            }
          });
        });
        cy.get('[data-cy=account-button]').first().click();
      } else {
        // Ingen accounts, opret en
        cy.get('[data-cy=create-account-button]').click();
        cy.get('[data-cy=account-name-input]').type('Test Konto');
        cy.get('[data-cy=create-account-submit-button]').click();
        
        // Vent på account creation og gem account_id
        cy.wait('@createAccount').then((interception) => {
          const accountId = interception.response.body.idAccount || interception.response.body.id;
          if (accountId) {
            cy.window().then((win) => {
              win.localStorage.setItem('account_id', String(accountId));
              cy.log('✅ Sat account_id i localStorage efter oprettelse:', accountId);
            });
          } else {
            cy.log('⚠️ Kunne ikke hente account_id fra response:', interception.response.body);
            throw new Error('Kunne ikke hente account_id fra account creation response');
          }
        });
      }
    });

    // Verificer redirect til dashboard
    cy.url().should('include', '/dashboard');
    cy.contains('Dashboard').should('be.visible');

    // ===== STEP 4: Naviger til transaktioner =====
    cy.get('[data-cy=nav-transactions]').click();
    cy.url().should('include', '/transactions');
    cy.contains('Transaktioner').should('be.visible');

    // ===== STEP 5: Opret manuel transaktion =====
    // Intercept requests FØR vi opretter transaktionen
    cy.intercept('POST', '**/transactions/**').as('createTransaction');
    cy.intercept('GET', '**/transactions/**').as('getTransactions');
    
    // Debug: Tjek hvad der er i localStorage først
    cy.window().then((win) => {
      cy.log('🔍 Debug localStorage:');
      cy.log('  token: ' + win.localStorage.getItem('access_token'));
      cy.log('  account_id: ' + win.localStorage.getItem('account_id'));
      
      // Verificer at account_id er sat
      const accountId = win.localStorage.getItem('account_id');
      if (!accountId) {
        throw new Error('account_id mangler i localStorage!');
      }
    });

    cy.get('[data-cy=add-transaction-button]').click();

    // Vent på at modal/form er synlig
    cy.get('[data-cy=transaction-form]').should('be.visible');

    // Vent på at kategorier er loaded (vent på at der er mere end bare "Vælg Kategori")
    cy.get('[data-cy=transaction-category]', { timeout: 10000 }).should('be.visible');
    cy.get('[data-cy=transaction-category] option').should('have.length.greaterThan', 1);
    
    // Udfyld transaktion form
    cy.get('[data-cy=transaction-amount]').type('500');
    cy.get('[data-cy=transaction-description]').type('Test udgift');
    
    // Vælg kategori - vent på at kategorier er loaded og vælg første tilgængelige
    cy.get('[data-cy=transaction-category]').then(($select) => {
      const options = $select.find('option');
      if (options.length > 1) {
        // Vælg første kategori (index 1, da 0 er "Vælg Kategori")
        const firstCategoryValue = options.eq(1).val();
        cy.log('Vælger kategori med værdi:', firstCategoryValue);
        cy.get('[data-cy=transaction-category]').select(firstCategoryValue);
        // Verificer at kategori er valgt
        cy.get('[data-cy=transaction-category]').should('have.value', firstCategoryValue);
      } else {
        throw new Error('Ingen kategorier fundet!');
      }
    });
    
    // Vælg dato (i går - ikke fremtid, backend tillader ikke fremtidige datoer)
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    const dateString = yesterday.toISOString().split('T')[0];
    cy.get('[data-cy=transaction-date]').clear().type(dateString);
    cy.log('Bruger dato:', dateString);
    
    // Vælg type (expense)
    cy.get('[data-cy=transaction-type-expense]').check();
    
    // Submit
    cy.get('[data-cy=submit-transaction]').click();

    // Vent på at transaktionen er oprettet (201 response)
    cy.wait('@createTransaction').its('response.statusCode').should('eq', 201);
    cy.log('✅ Transaktion oprettet succesfuldt!');

    // Tjek om der er en fejlbesked (hvis der er, fail testen)
    cy.get('body').then(($body) => {
      const hasError = $body.find('.error-message, .message-display.error, [class*="error"]').length > 0;
      
      if (hasError) {
        cy.get('.error-message, .message-display.error, [class*="error"]').first().then(($error) => {
          const errorText = $error.text();
          cy.log('❌ Fejlbesked fundet:', errorText);
          throw new Error(`Transaktion fejlede: ${errorText}`);
        });
      }
    });

    // Vent på at listen opdateres og transaktionen vises
    // Dette er mere robust end at vente på GET request, da listen kan refreshe på forskellige måder
    cy.get('[data-cy=transaction-list]', { timeout: 15000 }).should('be.visible');
    
    // Vent på at transaktionen vises i listen (beskrivelsen "Test udgift")
    // Dette venter på at listen faktisk er opdateret med den nye transaktion
    cy.get('[data-cy=transaction-list]').contains('Test udgift', { timeout: 15000 }).should('be.visible');
    cy.log('✅ Transaktion vises i listen!');
  });
});

