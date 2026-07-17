import apiClient from '../utils/apiClient';
import { parseApiError } from './errors';
import { CATEGORIZATION_SERVICE_URL } from '../config/serviceUrls';

// Ruter matcher categorization-service (ADR-003):
// list/create er nested under kategorien, update/delete er flade.

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

export async function createSubcategory(categoryId, data) {
  const response = await apiClient.post(
    `${CATEGORIZATION_SERVICE_URL}/categories/${categoryId}/subcategories`,
    data,
  );
  if (!response.ok) throw await parseApiError(response);
  return response.json();
}

export async function updateSubcategory(subcategoryId, data) {
  const response = await apiClient.put(
    `${CATEGORIZATION_SERVICE_URL}/subcategories/${subcategoryId}`,
    data,
  );
  if (!response.ok) throw await parseApiError(response);
  return response.json();
}

export async function deleteSubcategory(subcategoryId) {
  const response = await apiClient.delete(
    `${CATEGORIZATION_SERVICE_URL}/subcategories/${subcategoryId}`,
  );
  if (!response.ok) throw await parseApiError(response);
}
