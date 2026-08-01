import { useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { BarChart3 } from 'lucide-react';
import CategoryFilterPanel from '../components/CategoryFilterPanel/CategoryFilterPanel';
import CategorySpendingOverview from '../components/CategorySpendingOverview/CategorySpendingOverview';
import { useCategories } from '../hooks/useCategories';
import { usePeriodOverview } from '../hooks/usePeriodOverview';
import { formatDate, getYearOptions } from '../lib/formatters';
import './CategoriesPage.css';

function initialPeriod(searchParams, now) {
  const month = Number(searchParams.get('month'));
  const year = Number(searchParams.get('year'));
  const validYears = getYearOptions(3);
  return {
    month: month >= 1 && month <= 12 ? String(month).padStart(2, '0') : String(now.getMonth() + 1).padStart(2, '0'),
    year: validYears.includes(year) ? String(year) : String(now.getFullYear()),
  };
}

function CategoriesPage() {
  const { categories } = useCategories();
  const [searchParams] = useSearchParams();

  const now = new Date();
  const [initial] = useState(() => initialPeriod(searchParams, now));
  const [selectedMonth, setSelectedMonth] = useState(initial.month);
  const [selectedYear, setSelectedYear] = useState(initial.year);
  const requestedCategoryId = Number(searchParams.get('category'));
  const [selectedCategoryIds, setSelectedCategoryIds] = useState(
    Number.isInteger(requestedCategoryId) && requestedCategoryId > 0 ? [requestedCategoryId] : [],
  );
  const effectiveCategoryIds = useMemo(() => {
    if (!categories.length) return selectedCategoryIds;
    const expenseIds = new Set(
      categories.filter((cat) => cat.type === 'expense').map((cat) => cat.id),
    );
    return selectedCategoryIds.filter((id) => expenseIds.has(id));
  }, [categories, selectedCategoryIds]);

  const hasAccount = Boolean(localStorage.getItem('account_id'));

  const period = useMemo(
    () => ({
      month: parseInt(selectedMonth, 10),
      year: parseInt(selectedYear, 10),
    }),
    [selectedMonth, selectedYear],
  );

  const { overview, budgetSummary, loading, error } = usePeriodOverview({
    month: period.month,
    year: period.year,
    enabled: hasAccount,
  });

  const noAccount = !hasAccount;

  return (
    <div className="categories-page">
      <div className="categories-page-header">
        <div>
          <h2>Udgifter og budgetter</h2>
          {overview?.startDate && overview?.endDate && (
            <p className="categories-period-range">
              Budgetperiode: {formatDate(overview.startDate)} – {formatDate(overview.endDate)}
            </p>
          )}
        </div>
      </div>

      <CategoryFilterPanel
        selectedMonth={selectedMonth}
        setSelectedMonth={setSelectedMonth}
        selectedYear={selectedYear}
        setSelectedYear={setSelectedYear}
        categories={categories}
        selectedCategoryIds={effectiveCategoryIds}
        setSelectedCategoryIds={setSelectedCategoryIds}
        includeUncategorized
      />

      {noAccount ? (
        <div className="categories-no-account">
          <div className="no-account-icon"><BarChart3 aria-hidden="true" size={48} /></div>
          <h3>Ingen konto valgt</h3>
          <p>Vælg en konto for at se dit kategori-overblik med forbrug og budgetter.</p>
          <Link to="/account-selector" className="select-account-btn">
            Vælg konto
          </Link>
        </div>
      ) : error ? (
        <div className="categories-no-account">
          <h3>Kunne ikke hente data</h3>
          <p>{error}</p>
        </div>
      ) : (
        <CategorySpendingOverview
          expensesByCategory={overview?.expensesByCategory}
          budgetSummary={budgetSummary}
          selectedCategoryIds={effectiveCategoryIds}
          loading={loading}
        />
      )}
    </div>
  );
}

export default CategoriesPage;
