// P3-43 / ADR-0005: alle backend-kald er RELATIVE og går gennem frontendens egen nginx,
// som proxy_pass'er per path (services/frontend/nginx.conf). Browseren taler med præcis
// én origin, hvilket er hele pointen: det er forudsætningen for CSP, HttpOnly-cookie og
// én rate-limit-zone, og det er grunden til at de 11 CORSMiddleware kan fjernes.
//
// De tidligere `import.meta.env.VITE_*_SERVICE_URL`-fallbacks er væk med vilje. De så ud
// som konfigurerbarhed, men var det ikke: variablerne var ikke sat nogen steder — ikke i
// compose, ikke i k8s, ikke i Dockerfilen — og Vite inliner `import.meta.env` ved build,
// så de hardkodede localhost:800X var dem der reelt blev bygget ind i imaget. En
// konfigurerbarhed der ikke virker er værre end ingen, fordi den bliver troet på.
//
// I dev proxyer Vite de samme præfikser (vite.config.js). Bemærk at kun nginx-siden er
// vogtet af compose_check.py rule 5; vite-siden holdes i sync i hånden.

const GATEWAY_SERVICE_URL = '/api/v1';

// Bemærk /users-suffikset: user-services login/register kaldes som
// `${USER_SERVICE_URL}/login`, ikke `/users/login`. Formen er bevaret fra de absolutte
// URL'er, så kaldstederne er urørte.
const USER_SERVICE_URL = '/api/v1/users';

const TRANSACTION_SERVICE_URL = '/api/v1';

// Taksonomien (kategorier + subkategorier) ejes af categorization-service
// (ADR-003) — al kategori-CRUD går dertil.
const CATEGORIZATION_SERVICE_URL = '/api/v1';

const BUDGET_SERVICE_URL = '/api/v1';

const AI_SERVICE_URL = '/api/v1';

const ACCOUNT_SERVICE_URL = '/api/v1';

const GOAL_SERVICE_URL = '/api/v1';

const BANKING_SERVICE_URL = '/api/v1';

const NOTIFICATION_SERVICE_URL = '/api/v1';

export {
  GATEWAY_SERVICE_URL,
  USER_SERVICE_URL,
  TRANSACTION_SERVICE_URL,
  CATEGORIZATION_SERVICE_URL,
  BUDGET_SERVICE_URL,
  AI_SERVICE_URL,
  ACCOUNT_SERVICE_URL,
  GOAL_SERVICE_URL,
  BANKING_SERVICE_URL,
  NOTIFICATION_SERVICE_URL,
};
