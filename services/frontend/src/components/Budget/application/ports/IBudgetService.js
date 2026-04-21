/**
 * Inbound Port (Use Case Interface)
 * Definerer hvad applikationen kan gøre
 */

export class IBudgetService {
  /**
   * @abstract
   * @param {Budget} budget
   * @returns {Promise<Budget>}
   */
  async createBudget(budget) {
    throw new Error('Not implemented');
  }

  /**
   * @abstract
   * @param {Budget} budget
   * @returns {Promise<Budget>}
   */
  async updateBudget(budget) {
    throw new Error('Not implemented');
  }

  /**
   * @abstract
   * @param {number} budgetId
   * @returns {Promise<void>}
   */
  async deleteBudget(budgetId) {
    throw new Error('Not implemented');
  }

  /**
   * @abstract
   * @param {number} year
   * @returns {Promise<Budget[]>}
   */
  async getBudgetsByYear(year) {
    throw new Error('Not implemented');
  }

  /**
   * @abstract
   * @returns {Promise<Budget[]>}
   */
  async getAllBudgets() {
    throw new Error('Not implemented');
  }
}
