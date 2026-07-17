import { createCrudApi } from './crudFactory';
import { CATEGORIZATION_SERVICE_URL } from '../config/serviceUrls';

// Regler ejes af categorization-service (F1-02). Alle kald er
// JWT-scopede til den aktuelle bruger server-side — listen indeholder
// både brugeroprettede keyword-regler og lærte regler (is_learned).
const crud = createCrudApi('/rules', { baseUrl: CATEGORIZATION_SERVICE_URL });

export async function fetchRules() {
  return crud.fetchAll();
}

export async function createRule(data) {
  return crud.create(data);
}

export async function updateRule(id, data) {
  return crud.update(id, data);
}

export async function deleteRule(id) {
  return crud.remove(id);
}
