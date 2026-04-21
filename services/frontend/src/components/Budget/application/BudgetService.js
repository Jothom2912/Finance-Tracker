/**
 * Budget Application Service
 * Implementerer IBudgetService og koordinerer use cases
 */

import { IBudgetService } from './ports/IBudgetService';
import {
  BudgetValidationException,
  BudgetDuplicateException,
  BudgetNotFoundException,
  BudgetApiException
} from '../domain/exceptions';

export class BudgetService extends IBudgetService {
  /**
   * @param {IBudgetRepository} budgetRepository
   */
  constructor(budgetRepository) {
    super();
    this._budgetRepository = budgetRepository;
  }

  /**
   * Create a new budget
   * @param {Budget} budget
   * @returns {Promise<Budget>}
   */
  async createBudget(budget) {
    // Validate budget domain rules
    const validation = budget.validate();
    if (!validation.isValid) {
      throw new BudgetValidationException(validation.errors);
    }

    // Check for duplicates
    const existingBudgets = await this._budgetRepository.findByYear(budget.year);
    const hasDuplicate = existingBudgets.some(b => budget.isDuplicate(b));

    if (hasDuplicate) {
      throw new BudgetDuplicateException();
    }

    // Persist and return
    try {
      return await this._budgetRepository.save(budget);
    } catch (error) {
      throw new BudgetApiException(
        error.message || 'Kunne ikke oprette budget',
        error.statusCode
      );
    }
  }

  /**
   * Update an existing budget
   * @param {Budget} budget
   * @returns {Promise<Budget>}
   */
  async updateBudget(budget) {
    // Validate
    const validation = budget.validate();
    if (!validation.isValid) {
      throw new BudgetValidationException(validation.errors);
    }

    if (!budget.id) {
      throw new BudgetValidationException(['Budget ID er påkrævet for opdatering']);
    }

    // Check for duplicates (excluding self)
    const existingBudgets = await this._budgetRepository.findByYear(budget.year);
    const hasDuplicate = existingBudgets.some(b => budget.isDuplicate(b));

    if (hasDuplicate) {
      throw new BudgetDuplicateException();
    }

    try {
      return await this._budgetRepository.save(budget);
    } catch (error) {
      throw new BudgetApiException(
        error.message || 'Kunne ikke opdatere budget',
        error.statusCode
      );
    }
  }

  /**
   * Delete a budget
   * @param {number} budgetId
   * @returns {Promise<void>}
   */
  async deleteBudget(budgetId) {
    const budget = await this._budgetRepository.findById(budgetId);
    if (!budget) {
      throw new BudgetNotFoundException(budgetId);
    }

    try {
      await this._budgetRepository.delete(budgetId);
    } catch (error) {
      throw new BudgetApiException(
        error.message || 'Kunne ikke slette budget',
        error.statusCode
      );
    }
  }

  /**
   * Get budgets for a specific year
   * @param {number} year
   * @returns {Promise<Budget[]>}
   */
  async getBudgetsByYear(year) {
    try {
      return await this._budgetRepository.findByYear(year);
    } catch (error) {
      throw new BudgetApiException(
        error.message || `Kunne ikke hente budgetter for ${year}`,
        error.statusCode
      );
    }
  }

  /**
   * Get all budgets
   * @returns {Promise<Budget[]>}
   */
  async getAllBudgets() {
    try {
      return await this._budgetRepository.findAll();
    } catch (error) {
      throw new BudgetApiException(
        error.message || 'Kunne ikke hente budgetter',
        error.statusCode
      );
    }
  }
}
