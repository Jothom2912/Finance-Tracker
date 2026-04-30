/**
 * Domain-level exceptions
 */

export class BudgetException extends Error {
  constructor(message) {
    super(message);
    this.name = 'BudgetException';
  }
}

export class BudgetValidationException extends BudgetException {
  constructor(errors) {
    super(errors.join(', '));
    this.name = 'BudgetValidationException';
    this.errors = errors;
  }
}

export class BudgetNotFoundException extends BudgetException {
  constructor(budgetId) {
    super(`Budget with id ${budgetId} not found`);
    this.name = 'BudgetNotFoundException';
    this.budgetId = budgetId;
  }
}

export class BudgetDuplicateException extends BudgetException {
  constructor() {
    super('Der findes allerede et budget for denne kategori i den valgte periode.');
    this.name = 'BudgetDuplicateException';
  }
}

export class BudgetApiException extends BudgetException {
  constructor(message, statusCode) {
    super(message);
    this.name = 'BudgetApiException';
    this.statusCode = statusCode;
  }
}
