import { createCrudApi } from './crudFactory';
import { BUDGET_SERVICE_URL } from '../config/serviceUrls';

const crud = createCrudApi('/budgets', { baseUrl: BUDGET_SERVICE_URL, emptyOnNotFound: true });

export const fetchBudgets = crud.fetchAll;
export const createBudget = crud.create;
export const updateBudget = crud.update;
export const deleteBudget = crud.remove;
