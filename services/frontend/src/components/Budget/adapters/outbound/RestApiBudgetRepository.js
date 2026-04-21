/**
 * REST API Budget Repository Adapter
 * Implementerer IBudgetRepository med HTTP calls
 */

import { IBudgetRepository } from '../ports/IBudgetRepository';
import { Budget } from '../../domain/Budget';
import { BudgetApiException } from '../../domain/exceptions';
import apiClient from '../../../../utils/apiClient';

export class RestApiBudgetRepository extends IBudgetRepository {
  /**
   * @param {string} baseUrl - API base URL (default: '/budgets')
   */
  constructor(baseUrl = '/budgets') {
    super();
    this._baseUrl = baseUrl;
  }

  /**
   * Save (create or update) a budget
   * @param {Budget} budget
   * @returns {Promise<Budget>}
   */
  async save(budget) {
    try {
      const isCreating = !budget.id;
      const url = isCreating ? this._baseUrl : `${this._baseUrl}/${budget.id}`;
      const method = isCreating ? 'post' : 'put';

      const response = await apiClient[method](url, budget.toApiRequest());

      if (!response.ok) {
        const errorData = await response.json();
        const errorMessage = this._extractErrorMessage(errorData);
        throw new BudgetApiException(errorMessage, response.status);
      }

      const data = await response.json();
      return Budget.fromApiResponse(data);
    } catch (error) {
      if (error instanceof BudgetApiException) {
        throw error;
      }
      throw new BudgetApiException(
        error.message || 'Fejl ved gemning af budget',
        error.statusCode
      );
    }
  }

  /**
   * Find budget by ID
   * @param {number} budgetId
   * @returns {Promise<Budget|null>}
   */
  async findById(budgetId) {
    try {
      const response = await apiClient.get(`${this._baseUrl}/${budgetId}`);

      if (response.status === 404) {
        return null;
      }

      if (!response.ok) {
        const errorData = await response.json();
        const errorMessage = this._extractErrorMessage(errorData);
        throw new BudgetApiException(errorMessage, response.status);
      }

      const data = await response.json();
      return Budget.fromApiResponse(data);
    } catch (error) {
      if (error instanceof BudgetApiException) {
        throw error;
      }
      throw new BudgetApiException(
        error.message || `Kunne ikke hente budget ${budgetId}`,
        error.statusCode
      );
    }
  }

  /**
   * Find budgets by year
   * @param {number} year
   * @returns {Promise<Budget[]>}
   */
  async findByYear(year) {
    try {
      const response = await apiClient.get(`${this._baseUrl}/?year=${year}`);

      if (response.status === 404) {
        return [];
      }

      if (!response.ok) {
        const errorData = await response.json();
        const errorMessage = this._extractErrorMessage(errorData);
        throw new BudgetApiException(errorMessage, response.status);
      }

      const data = await response.json();
      return Array.isArray(data) ? data.map(item => Budget.fromApiResponse(item)) : [];
    } catch (error) {
      if (error instanceof BudgetApiException) {
        throw error;
      }
      throw new BudgetApiException(
        error.message || `Kunne ikke hente budgetter for år ${year}`,
        error.statusCode
      );
    }
  }

  /**
   * Find all budgets
   * @returns {Promise<Budget[]>}
   */
  async findAll() {
    try {
      const response = await apiClient.get(this._baseUrl);

      if (!response.ok) {
        const errorData = await response.json();
        const errorMessage = this._extractErrorMessage(errorData);
        throw new BudgetApiException(errorMessage, response.status);
      }

      const data = await response.json();
      return Array.isArray(data) ? data.map(item => Budget.fromApiResponse(item)) : [];
    } catch (error) {
      if (error instanceof BudgetApiException) {
        throw error;
      }
      throw new BudgetApiException(
        error.message || 'Kunne ikke hente budgetter',
        error.statusCode
      );
    }
  }

  /**
   * Delete a budget
   * @param {number} budgetId
   * @returns {Promise<void>}
   */
  async delete(budgetId) {
    try {
      const response = await apiClient.delete(`${this._baseUrl}/${budgetId}`);

      if (!response.ok) {
        const errorData = await response.json();
        const errorMessage = this._extractErrorMessage(errorData);
        throw new BudgetApiException(errorMessage, response.status);
      }
    } catch (error) {
      if (error instanceof BudgetApiException) {
        throw error;
      }
      throw new BudgetApiException(
        error.message || `Kunne ikke slette budget ${budgetId}`,
        error.statusCode
      );
    }
  }

  /**
   * Extract user-friendly error message from API response
   * @private
   * @param {Object} errorData
   * @returns {string}
   */
  _extractErrorMessage(errorData) {
    if (errorData.detail) {
      if (Array.isArray(errorData.detail)) {
        return errorData.detail.map(d => d.msg).join(', ');
      }
      return errorData.detail;
    }
    return 'En ukendt fejl opstod';
  }
}
