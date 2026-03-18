# Cypress E2E Tests

Denne mappe indeholder end-to-end tests for Finans Tracker applikationen.

## Installation

Først skal du installere Cypress:

```bash
cd frontend/finans-tracker-frontend
npm install
```

## Kørsel af tests

### Åbn Cypress Test Runner (interaktiv)

```bash
npm run cypress:open
```

Dette åbner Cypress Test Runner hvor du kan vælge hvilke tests du vil køre og se dem køre i en browser.

### Kør tests headless (CI/CD)

```bash
npm run cypress:run
```

Dette kører alle tests i headless mode (uden browser UI).

## Forudsætninger

Før du kører tests, skal du sikre dig at:

1. **Backend API kører** på `http://localhost:8000`
2. **Frontend kører** på `http://localhost:3000`
3. **Database er sat op** med kategorier (kør `seed_categories.py`)

## Test Struktur

### `cypress/e2e/user-flow.cy.js`
Komplet bruger flow test:
- Opret bruger
- Log ind
- Vælg/opret konto
- Naviger til dashboard
- Opret manuel transaktion

### `cypress/e2e/csv-upload.cy.js`
CSV upload test:
- Opret bruger og log ind
- Upload CSV fil med transaktioner
- Verificer at transaktioner er importeret

## Custom Commands

Cypress custom commands er defineret i `cypress/support/commands.js`:

- `cy.login(email, password)` - Logger en bruger ind
- `cy.register(userData)` - Opretter en ny bruger
- `cy.selectOrCreateAccount(accountName)` - Vælger eller opretter en konto

## Fixtures

Test data fixtures findes i `cypress/fixtures/`:

- `test-transactions.csv` - Eksempel CSV fil med transaktioner til upload test

## Data-cy Attributter

Alle testbare elementer har `data-cy` attributter for stabil test selektion:

- `data-cy="email-input"` - Email input felt
- `data-cy="password-input"` - Password input felt
- `data-cy="login-button"` - Login knap
- `data-cy="nav-transactions"` - Navigation link til transaktioner
- `data-cy="add-transaction-button"` - Knap til at tilføje ny transaktion
- `data-cy="transaction-amount"` - Beløb input i transaktionsformular
- `data-cy="csv-upload-input"` - CSV upload input
- osv.

## Troubleshooting

### Tests fejler med "element not found"
- Tjek at frontend kører på port 3000
- Tjek at backend kører på port 8000
- Tjek at du har kategorier i databasen

### CSV upload fejler
- Tjek at CSV fil formatet matcher backend forventninger
- Tjek backend logs for fejlbeskeder

### Login fejler
- Tjek at backend authentication virker
- Tjek at test bruger data er korrekt

