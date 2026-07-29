import { createCrudApi } from './crudFactory';
import { CATEGORIZATION_SERVICE_URL } from '../config/serviceUrls';

// Read-only. Taksonomien er delt state og skrives kun af
// categorization-service selv, bag X-Internal-API-Key (P2-28) — der er
// ingen bruger-sti at kalde. Kun `fetchAll` bruges herfra; factoryen har
// andre forbrugere og bliver stående.
const crud = createCrudApi('/categories', {
  baseUrl: CATEGORIZATION_SERVICE_URL,
  trailingSlash: true,
});

export async function fetchCategories(params) {
  return crud.fetchAll(params);
}
