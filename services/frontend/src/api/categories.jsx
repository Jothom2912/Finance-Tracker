import { createCrudApi } from './crudFactory';
import { CATEGORIZATION_SERVICE_URL } from '../config/serviceUrls';

const crud = createCrudApi('/categories', {
  baseUrl: CATEGORIZATION_SERVICE_URL,
  trailingSlash: true,
});

export async function fetchCategories(params) {
  return crud.fetchAll(params);
}

export async function createCategory(data) {
  return crud.create(data);
}

export async function updateCategory(id, data) {
  return crud.update(id, data);
}

export async function deleteCategory(id) {
  return crud.remove(id);
}
