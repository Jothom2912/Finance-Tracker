import { useState, useCallback } from 'react';
import * as transactionsApi from '../api/transactions';

export function useTransactions() {
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetch = useCallback(async (filters) => {
    setLoading(true);
    setError(null);
    try {
      const data = await transactionsApi.fetchTransactions(filters);
      setTransactions(data);
      return data;
    } catch (err) {
      setError(err.message || 'Kunne ikke hente transaktioner.');
      return [];
    } finally {
      setLoading(false);
    }
  }, []);

  const create = useCallback(async (data) => {
    const result = await transactionsApi.createTransaction(data);
    return result;
  }, []);

  const update = useCallback(async (id, data) => {
    const result = await transactionsApi.updateTransaction(id, data);
    return result;
  }, []);

  const remove = useCallback(async (id) => {
    await transactionsApi.deleteTransaction(id);
  }, []);

  const uploadCsv = useCallback(async (file) => {
    const result = await transactionsApi.uploadTransactionsCsv(file);
    return result;
  }, []);

  return { transactions, loading, error, fetch, create, update, remove, uploadCsv };
}
