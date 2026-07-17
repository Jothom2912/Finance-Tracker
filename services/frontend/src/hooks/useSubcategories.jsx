import { useQuery } from '@tanstack/react-query';
import { fetchAllSubcategories, fetchSubcategories } from '../api/subcategories';

export function subcategoriesQueryKey(categoryId) {
  return ['subcategories', categoryId];
}

// Flad liste over ALLE underkategorier (den dedikerede list-all-rute,
// undgår N+1 per kategori). Bruges af inline-kategorivælgeren i
// transaktionslisten og regel-formularens kaskade-uafhængige visning.
export function useAllSubcategories() {
  const query = useQuery({
    queryKey: ['subcategories', 'all'],
    queryFn: () => fetchAllSubcategories(),
  });

  return {
    subcategories: query.data ?? [],
    loading: query.isLoading,
    error: query.error
      ? query.error.message || 'Kunne ikke hente underkategorier.'
      : null,
  };
}

// Per-kategori-hook (ikke et samlet tree): kaskade-pickeren og
// management-UI'et bruger én kategori ad gangen, og react-query
// cacher per kategori-id. Dashboardet får subkategorier embedded
// i GraphQL-svaret og bruger ikke denne hook.
export function useSubcategories(categoryId) {
  const query = useQuery({
    queryKey: subcategoriesQueryKey(categoryId),
    queryFn: () => fetchSubcategories(categoryId),
    enabled: !!categoryId,
  });

  return {
    subcategories: query.data ?? [],
    loading: query.isLoading,
    error: query.error
      ? query.error.message || 'Kunne ikke hente underkategorier.'
      : null,
  };
}
