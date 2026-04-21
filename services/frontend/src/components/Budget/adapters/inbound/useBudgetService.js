/**
 * useBudgetService Hook
 * Adapter between React components and BudgetService
 */

import { useState, useCallback, useEffect } from 'react';
import { BudgetService } from '../../application/BudgetService';
import { RestApiBudgetRepository } from '../outbound/RestApiBudgetRepository';
import {
  BudgetValidationException,
  BudgetDuplicateException,
  BudgetApiException
} from '../../domain/exceptions';

/**
 * Initialize budget service with repository
 * @private
 */
function initializeBudgetService() {
  const repository = new RestApiBudgetRepository();
  return new BudgetService(repository);
}

/**
 * Custom hook for budget operations
 * Provides state management and error handling
 * @returns {Object} { budgets, loading, error, actions }
 */
export function useBudgetService() {
  const [budgets, setBudgets] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);

  const service = initializeBudgetService();

  // Clear messages after a delay
  useEffect(() => {
    if (error || successMessage) {
      const timer = setTimeout(() => {
        setError(null);
        setSuccessMessage(null);
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [error, successMessage]);

  /**
   * Fetch budgets by year
   */
  const fetchBudgetsByYear = useCallback(async (year) => {
    setLoading(true);
    setError(null);
    try {
      const result = await service.getBudgetsByYear(year);
      setBudgets(result);
      return result;
    } catch (err) {
      const errorMessage = err.message || 'Kunne ikke hente budgetter';
      setError(errorMessage);
      setBudgets([]);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [service]);

  /**
   * Create a new budget
   */
  const createBudget = useCallback(async (budget) => {
    setLoading(true);
    setError(null);

    try {
      const created = await service.createBudget(budget);
      setSuccessMessage('Budget oprettet!');
      // Refresh the budgets list
      await fetchBudgetsByYear(budget.year);
      return created;
    } catch (err) {
      if (err instanceof BudgetValidationException) {
        setError(err.errors.join('\n'));
      } else if (err instanceof BudgetDuplicateException) {
        setError(err.message);
      } else if (err instanceof BudgetApiException) {
        setError(err.message);
      } else {
        setError(err.message || 'Kunne ikke oprette budget');
      }
      throw err;
    } finally {
      setLoading(false);
    }
  }, [service, fetchBudgetsByYear]);

  /**
   * Update an existing budget
   */
  const updateBudget = useCallback(async (budget) => {
    setLoading(true);
    setError(null);

    try {
      const updated = await service.updateBudget(budget);
      setSuccessMessage('Budget opdateret!');
      // Refresh the budgets list
      await fetchBudgetsByYear(budget.year);
      return updated;
    } catch (err) {
      if (err instanceof BudgetValidationException) {
        setError(err.errors.join('\n'));
      } else if (err instanceof BudgetDuplicateException) {
        setError(err.message);
      } else if (err instanceof BudgetApiException) {
        setError(err.message);
      } else {
        setError(err.message || 'Kunne ikke opdatere budget');
      }
      throw err;
    } finally {
      setLoading(false);
    }
  }, [service, fetchBudgetsByYear]);

  /**
   * Delete a budget
   */
  const deleteBudget = useCallback(async (budgetId, year) => {
    setLoading(true);
    setError(null);

    try {
      await service.deleteBudget(budgetId);
      setSuccessMessage('Budget slettet!');
      // Refresh the budgets list
      await fetchBudgetsByYear(year);
    } catch (err) {
      if (err instanceof BudgetApiException) {
        setError(err.message);
      } else {
        setError(err.message || 'Kunne ikke slette budget');
      }
      throw err;
    } finally {
      setLoading(false);
    }
  }, [service, fetchBudgetsByYear]);

  /**
   * Clear error message
   */
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  /**
   * Clear success message
   */
  const clearSuccessMessage = useCallback(() => {
    setSuccessMessage(null);
  }, []);

  return {
    // State
    budgets,
    loading,
    error,
    successMessage,

    // Actions
    fetchBudgetsByYear,
    createBudget,
    updateBudget,
    deleteBudget,
    clearError,
    clearSuccessMessage
  };
}
