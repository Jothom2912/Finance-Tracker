import { useEffect, useState } from 'react';

// Debounce af et input: query-keys må først skifte når input er faldet
// til ro, ellers fyres et søge-request per tastetryk.
export function useDebouncedValue(value, delayMs = 300) {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);

  return debounced;
}
