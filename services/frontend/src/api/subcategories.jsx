import apiClient from '../utils/apiClient';
import { parseApiError } from './errors';
import { CATEGORIZATION_SERVICE_URL } from '../config/serviceUrls';

// Read-only. Ruter matcher categorization-service (ADR-003): list er
// nested under kategorien, list-all er flad. Skrive-ruterne ligger under
// /api/v1/internal bag X-Internal-API-Key (P2-28) og er ikke kaldbare
// herfra — perimeteren svarer 404 på præfikset.

export async function fetchAllSubcategories() {
  const response = await apiClient.get(`${CATEGORIZATION_SERVICE_URL}/subcategories/`);
  if (!response.ok) throw await parseApiError(response);
  return response.json();
}

export async function fetchSubcategories(categoryId) {
  const response = await apiClient.get(
    `${CATEGORIZATION_SERVICE_URL}/categories/${categoryId}/subcategories`,
  );
  if (!response.ok) throw await parseApiError(response);
  return response.json();
}
