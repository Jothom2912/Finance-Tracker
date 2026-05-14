import { createCrudApi } from './crudFactory';
import { GOAL_SERVICE_URL } from '../config/serviceUrls';

const crud = createCrudApi('/goals', { baseUrl: GOAL_SERVICE_URL, emptyOnNotFound: true });

export const fetchGoals = crud.fetchAll;
export const createGoal = crud.create;
export const updateGoal = crud.update;
export const deleteGoal = crud.remove;
