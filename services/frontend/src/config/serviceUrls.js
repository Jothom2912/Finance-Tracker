const MONOLITH_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

const GATEWAY_SERVICE_URL =
  import.meta.env.VITE_GATEWAY_SERVICE_URL || 'http://localhost:8010/api/v1';

const USER_SERVICE_URL =
  import.meta.env.VITE_USER_SERVICE_URL || 'http://localhost:8001/api/v1/users';

const TRANSACTION_SERVICE_URL =
  import.meta.env.VITE_TRANSACTION_SERVICE_URL || 'http://localhost:8002/api/v1';

const BUDGET_SERVICE_URL =
  import.meta.env.VITE_BUDGET_SERVICE_URL || 'http://localhost:8003/api/v1';

const AI_SERVICE_URL =
  import.meta.env.VITE_AI_SERVICE_URL || 'http://localhost:8007/api/v1';

const ACCOUNT_SERVICE_URL =
  import.meta.env.VITE_ACCOUNT_SERVICE_URL || 'http://localhost:8004/api/v1';

const GOAL_SERVICE_URL =
  import.meta.env.VITE_GOAL_SERVICE_URL || 'http://localhost:8006/api/v1';

const BANKING_SERVICE_URL =
  import.meta.env.VITE_BANKING_SERVICE_URL || 'http://localhost:8009/api/v1';

export {
  MONOLITH_URL,
  GATEWAY_SERVICE_URL,
  USER_SERVICE_URL,
  TRANSACTION_SERVICE_URL,
  BUDGET_SERVICE_URL,
  AI_SERVICE_URL,
  ACCOUNT_SERVICE_URL,
  GOAL_SERVICE_URL,
  BANKING_SERVICE_URL,
};
