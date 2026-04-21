/**
 * Outbound Port (Repository Interface)
 * Definerer hvordan data persisteres
 */

export class IBudgetRepository {
  /**
   * @abstract
   * @param {Budget} budget
   * @returns {Promise<Budget>}
   */
  async save(budget) {
    throw new Error('Not implemented');
  }

  /**
   * @abstract
   * @param {number} budgetId
   * @returns {Promise<Budget|null>}
   */
  async findById(budgetId) {
    throw new Error('Not implemented');
  }

  /**
   * @abstract
   * @param {number} year
   * @returns {Promise<Budget[]>}
   */
  async findByYear(year) {
    throw new Error('Not implemented');
  }

  /**
   * @abstract
   * @returns {Promise<Budget[]>}
   */
  async findAll() {
    throw new Error('Not implemented');
  }

  /**
   * @abstract
   * @param {number} budgetId
   * @returns {Promise<void>}
   */
  async delete(budgetId) {
    throw new Error('Not implemented');
  }
}
