/**
 * Budget Domain Entity
 * Indeholder kun forretningslogik og validering
 */
export class Budget {
  constructor({
    id,
    category_id,
    amount,
    month,
    year,
    budget_date,
    categories = []
  }) {
    this.id = id;
    this.category_id = category_id;
    this.amount = amount;
    this.month = month;
    this.year = year;
    this.budget_date = budget_date;
    this.categories = categories;
  }

  /**
   * Valider budget data
   * @returns {Object} { isValid: boolean, errors: string[] }
   */
  validate() {
    const errors = [];

    if (!this.category_id || this.category_id <= 0) {
      errors.push('Vælg venligst en kategori.');
    }

    if (!this.amount || this.amount <= 0) {
      errors.push('Beløb skal være et positivt tal.');
    }

    if (!this.month || !this.year) {
      errors.push('Vælg venligst måned og år.');
    }

    return {
      isValid: errors.length === 0,
      errors
    };
  }

  /**
   * Tjek om denne budget kolliderer med en anden
   */
  isDuplicate(otherBudget) {
    return (
      this.category_id === otherBudget.category_id &&
      this.month === otherBudget.month &&
      this.year === otherBudget.year &&
      (!this.id || this.id !== otherBudget.id)
    );
  }

  /**
   * Normaliser budget data fra API response
   */
  static fromApiResponse(data) {
    let month = '';
    let yearStr = '';

    if (data.budget_date) {
      const budgetDate = new Date(data.budget_date);
      month = String(budgetDate.getMonth() + 1).padStart(2, '0');
      yearStr = String(budgetDate.getFullYear());
    }

    const categoryId =
      data.categories?.[0]?.idCategory ||
      data.Category_idCategory ||
      data.category_id;

    return new Budget({
      id: data.idBudget || data.id,
      category_id: categoryId,
      amount: data.amount,
      month: month || data.month,
      year: yearStr || data.year,
      budget_date: data.budget_date,
      categories: data.categories || []
    });
  }

  /**
   * Konverter til API request format
   */
  toApiRequest() {
    return {
      category_id: this.category_id,
      amount: this.amount,
      month: this.month,
      year: this.year
    };
  }
}
