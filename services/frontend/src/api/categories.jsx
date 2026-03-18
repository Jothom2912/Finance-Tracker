import { createCrudApi } from './crudFactory';

const crud = createCrudApi('/categories');

export const fetchCategories = crud.fetchAll;
export const createCategory = crud.create;
export const updateCategory = crud.update;
export const deleteCategory = crud.remove;
