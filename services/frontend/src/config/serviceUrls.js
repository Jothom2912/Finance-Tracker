const MONOLITH_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

const USER_SERVICE_URL =
  import.meta.env.VITE_USER_SERVICE_URL || 'http://localhost:8001/api/v1/users';

const TRANSACTION_SERVICE_URL =
  import.meta.env.VITE_TRANSACTION_SERVICE_URL || 'http://localhost:8002/api/v1';

const BUDGET_SERVICE_URL =
  import.meta.env.VITE_BUDGET_SERVICE_URL || 'http://localhost:8003/api/v1';

export { MONOLITH_URL, USER_SERVICE_URL, TRANSACTION_SERVICE_URL, BUDGET_SERVICE_URL };
