import { createCrudApi } from './crudFactory';

const crud = createCrudApi('/goals', { emptyOnNotFound: true });

export const fetchGoals = crud.fetchAll;
export const createGoal = crud.create;
export const updateGoal = crud.update;
export const deleteGoal = crud.remove;
