# Finance Tracker Frontend

React 18 SPA built with Vite 5 for personal finance tracking. Connects to the monolith backend (port 8000) for analytics, bank connections, and transaction management via REST and GraphQL.

Package manager: npm only. `package-lock.json` is the source of truth for this frontend; do not use Yarn here.

## Quick Start

```bash
# Install dependencies
npm install

# Start development server
npm run dev
```

App: http://localhost:3001

## Tech Stack

| Technology | Purpose |
|-----------|---------|
| React 18 | UI framework |
| Vite 5 | Build tool and dev server |
| react-router-dom v7 | Client-side routing |
| graphql-request | GraphQL client for dashboard reads |
| Recharts 3 | Charts (pie, bar, area) |
| Vitest + Testing Library | Unit tests (96 tests) |
| CSS Variables | Design tokens, no Tailwind |

## Project Structure

```
src/
├── api/                    # API client modules
│   ├── graphqlClient.jsx   # GraphQL client (analytics reads)
│   ├── bank.jsx            # Bank REST API (connections, sync)
│   ├── transactions.jsx    # Transaction CRUD
│   ├── categories.jsx      # Category CRUD
│   ├── accounts.jsx        # Account CRUD
│   ├── budgets.jsx         # Budget CRUD
│   ├── goals.jsx           # Goal CRUD
│   ├── dashboard.jsx       # Dashboard REST API
│   └── auth.jsx            # Authentication
├── components/
│   ├── DashboardOverview/  # Main dashboard layout
│   ├── BankConnectionWidget/ # Bank status + sync button
│   ├── MonthlyExpensesTrend/ # Expenses trend area chart
│   ├── SummaryCards/       # KPI cards (income, expenses, net, balance)
│   ├── RecentTransactions/ # Last 10 transactions with tier badges
│   ├── BudgetProgressSection/ # Budget progress bars
│   ├── GoalProgressSection/ # Goal progress cards
│   └── CategoryExpensesList/ # Category breakdown
├── Charts/
│   ├── PieChart.jsx        # Category expenses pie chart
│   └── CategoryBarChart.jsx # Category bar chart
├── hooks/
│   └── useDashboardData/   # Dashboard data hook (GraphQL)
├── pages/                  # Route page components
├── context/                # Auth context provider
├── lib/
│   └── formatters.jsx      # Amount/date formatting (da-DK locale)
└── utils/
    └── apiClient.jsx       # Base REST client with auth headers
```

## Dashboard Architecture

The dashboard uses a **REST for mutations, GraphQL for reads** pattern:

- **GraphQL** (`useDashboardData` hook) fetches all read-only dashboard data in a single query: financial overview, budget summary, goal progress, recent transactions (with `categorizationTier`), and monthly expenses trend.
- **REST** (`api/bank.jsx`) handles bank sync mutations which have side effects (fetch from external API, categorize, store).

After a bank sync, the dashboard auto-refreshes via a `refreshKey` mechanism so new transactions appear immediately.

### Key Dashboard Components

**BankConnectionWidget** — Shows connected banks with status indicator, IBAN suffix, time since last sync, and a sync button. The sync button disables during sync and shows an inline result toast ("12 nye, 3 duplikater") instead of a browser alert.

**MonthlyExpensesTrend** — Recharts AreaChart showing the last 6 months of expenses. Months without data render as 0 (no gaps in the graph). Uses a gradient fill and custom tooltip with `da-DK` formatted amounts.

**RecentTransactions** — Lists the 10 most recent transactions with categorization tier badges:
- `auto` (green) — matched by rule engine
- `fallback` (yellow) — no match, used default category
- `ml` / `llm` (blue) — matched by ML or LLM tier (future)

## API Clients

| Module | Protocol | Base URL |
|--------|----------|----------|
| `api/graphqlClient.jsx` | GraphQL | `/api/v1/graphql` |
| `api/bank.jsx` | REST | `/api/v1/bank/*` |
| `utils/apiClient.jsx` | REST | `/api/v1/*` (generic) |

All clients automatically attach `Authorization: Bearer <token>` and `X-Account-ID` headers from localStorage.

## Commands

```bash
npm run dev          # Start dev server (port 3001)
npm run build        # Production build
npm run preview      # Preview production build
npm test             # Run all tests (vitest run)
npm run test:watch   # Run tests in watch mode
```

## Design Tokens

Styling uses CSS custom properties defined in `src/index.css`. No Tailwind CSS.

| Token | Purpose |
|-------|---------|
| `--color-brand-*` | Primary identity colors |
| `--color-success-*` | Positive amounts, active states |
| `--color-error-*` | Negative amounts, expenses |
| `--color-warning-*` | Warnings, fallback badges |
| `--color-bg-surface` | Card backgrounds |
| `--color-bg-base` | Page background |
| `--radius-md/lg` | Border radius scale |
| `--shadow-sm/md/lg` | Box shadow scale |
| `--font-size-xs..3xl` | Typography scale |

## Visual QA Checklist

Use this checklist before merging UI changes to keep the design direction consistent.

### Tokens and Colors

- Use CSS tokens from `src/index.css` for brand, text, borders, radius, and shadows.
- Avoid new hardcoded hex colors unless a new token is added first.
- Keep semantic colors clear: green for positive, red for negative, amber for warnings.

### Layout and Surfaces

- Keep page background toned (`--color-bg-base`) and cards/modals white (`--color-bg-surface`).
- Use the shared radius scale (`--radius-md`, `--radius-lg`, `--radius-xl`).
- Prefer soft shadows (`--shadow-sm`, `--shadow-md`, `--shadow-lg`) over heavy hard-edged shadows.

### Typography and Spacing

- Use the token font sizes (`--font-size-sm` to `--font-size-3xl`) to keep hierarchy predictable.
- Keep section spacing generous so numbers are easy to scan.
- Avoid adding one-off text sizes unless there is a strong reason.

### Interaction and Accessibility

- Make sure hover and `:focus-visible` states match for key buttons and links.
- Keep focus rings visible and never remove them.
- Verify reduced motion: animations should be minimal when `prefers-reduced-motion` is enabled.
