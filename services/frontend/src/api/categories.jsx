import { createCrudApi } from './crudFactory';
import { TRANSACTION_SERVICE_URL } from '../config/serviceUrls';

const crud = createCrudApi('/categories', {
  baseUrl: TRANSACTION_SERVICE_URL,
  trailingSlash: true,
});

function fromServiceResponse(cat) {
  return {
    ...cat,
    idCategory: cat.id,
  };
}

export async function fetchCategories(params) {
  const data = await crud.fetchAll(params);
  return data.map(fromServiceResponse);
}

export async function createCategory(data) {
  const result = await crud.create(data);
  return fromServiceResponse(result);
}

export async function updateCategory(id, data) {
  const result = await crud.update(id, data);
  return fromServiceResponse(result);
}

export async function deleteCategory(id) {
  return crud.remove(id);
}
