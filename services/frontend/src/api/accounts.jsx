import { createCrudApi } from './crudFactory';

const crud = createCrudApi('/accounts', { trailingSlash: false });

export const fetchAccounts = crud.fetchAll;
export const createAccount = crud.create;
export const updateAccount = crud.update;
