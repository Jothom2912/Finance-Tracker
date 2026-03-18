import { useState, useEffect, useCallback } from 'react';
import { fetchCategories as apiFetchCategories } from '../api/categories';

export function useCategories() {
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetchCategories();
      setCategories(data);
    } catch (err) {
      setError(err.message || 'Kunne ikke hente kategorier.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { categories, loading, error, refresh };
}
