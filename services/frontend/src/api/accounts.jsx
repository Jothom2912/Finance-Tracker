import { createCrudApi } from './crudFactory';
import { ACCOUNT_SERVICE_URL } from '../config/serviceUrls';

const crud = createCrudApi('/accounts', { baseUrl: ACCOUNT_SERVICE_URL, trailingSlash: false });

export const fetchAccounts = crud.fetchAll;
export const createAccount = crud.create;
export const updateAccount = crud.update;
