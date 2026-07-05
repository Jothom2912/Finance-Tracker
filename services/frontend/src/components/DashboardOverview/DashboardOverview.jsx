import { useCallback, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import CategoryPieChart from '../../Charts/PieChart';
import SummaryCards from '../SummaryCards/SummaryCards';
import CategoryExpensesList from '../CategoryExpensesList/CategoryExpensesList';
import CategoryDrilldown from '../CategoryDrilldown/CategoryDrilldown';
import BudgetProgressSection from '../BudgetProgressSection/BudgetProgressSection';
import GoalProgressSection from '../GoalProgressSection/GoalProgressSection';
import RecentTransactions from '../RecentTransactions/RecentTransactions';
import BankConnectionWidget from '../BankConnectionWidget/BankConnectionWidget';
import MonthlyExpensesTrend from '../MonthlyExpensesTrend/MonthlyExpensesTrend';
import { useDashboardData } from '../../hooks/useDashboardData/useDashboardData';
import { MONTH_OPTIONS, getYearOptions, getMonthLabel } from '../../lib/formatters';
import './DashboardOverview.css';

function DashboardOverview() {
  const queryClient = useQueryClient();

  const now = new Date();
  const [selectedMonth, setSelectedMonth] = useState(now.getMonth() + 1);
  const [selectedYear, setSelectedYear] = useState(now.getFullYear());
  const [drilldownCategoryId, setDrilldownCategoryId] = useState(null);
  const yearOptions = useMemo(() => getYearOptions(3), []);

  const forceRefresh = useCallback(async () => {
    const refresh = () => {
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
    };
    refresh();
    // Gateway aggregates data from multiple services; allow brief propagation delay.
    await new Promise((resolve) => setTimeout(resolve, 2500));
    refresh();
  }, [queryClient]);

  const {
    overview,
    budgetSummary,
    goals,
    recentTransactions,
    expensesByMonth,
    loading,
    error,
    processedCategoryData,
    categoryDataWithPercentages,
    formatAmount,
  } = useDashboardData({ month: selectedMonth, year: selectedYear });

  const handlePeriodChange = (month, year) => {
    setSelectedMonth(month);
    setSelectedYear(year);
    // Drill-down peger på den gamle periodes data — nulstil.
    setDrilldownCategoryId(null);
  };

  // 'Ukategoriseret'-bucketen har id null — sentinel adskiller den fra
  // "ingen drill-down".
  const UNCATEGORIZED_KEY = 'uncategorized';
  const toDrilldownKey = (id) => (id == null ? UNCATEGORIZED_KEY : id);

  const drilldownCategory = useMemo(() => {
    if (drilldownCategoryId == null) return null;
    return (
      categoryDataWithPercentages.find((c) => toDrilldownKey(c.id) === drilldownCategoryId) ?? null
    );
  }, [categoryDataWithPercentages, drilldownCategoryId]);

  if (loading) return <div className="dashboard-loading">Indlæser dashboard...</div>;
  if (error) return <div className="dashboard-error">Fejl: {error}</div>;
  if (!overview) {
    return (
      <div className="dashboard-no-data">
        <p>Ingen data tilgængelige.</p>
        <Link to="/transactions" className="empty-state-link">
          Tilføj din første transaktion
        </Link>
      </div>
    );
  }

  const monthLabel = getMonthLabel(String(selectedMonth).padStart(2, '0'));

  const renderChart = () => {
    if (!processedCategoryData || processedCategoryData.length === 0) {
      return (
        <div className="no-chart-data">
          <p>Ingen udgiftsdata at vise denne måned.</p>
        </div>
      );
    }

    return (
      <div className="pie-chart-container">
        <CategoryPieChart
          data={processedCategoryData}
          colors={categoryDataWithPercentages.map((item) => item.color)}
          onSliceClick={(entry) => setDrilldownCategoryId(toDrilldownKey(entry?.id))}
        />
      </div>
    );
  };

  return (
    <div className="dashboard-overview-container">
      <div className="dashboard-header">
        <h2 className="dashboard-title">
          {monthLabel} {selectedYear}
        </h2>
        <div className="dashboard-period-selector">
          <label htmlFor="dash-month" className="visually-hidden">Måned</label>
          <select
            id="dash-month"
            className="period-select"
            value={selectedMonth}
            onChange={(e) => handlePeriodChange(parseInt(e.target.value, 10), selectedYear)}
          >
            {MONTH_OPTIONS.map((m) => (
              <option key={m.value} value={parseInt(m.value, 10)}>{m.label}</option>
            ))}
          </select>
          <label htmlFor="dash-year" className="visually-hidden">År</label>
          <select
            id="dash-year"
            className="period-select"
            value={selectedYear}
            onChange={(e) => handlePeriodChange(selectedMonth, parseInt(e.target.value, 10))}
          >
            {yearOptions.map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
        </div>
      </div>

      <SummaryCards
        totalIncome={overview.totalIncome}
        totalExpenses={overview.totalExpenses}
        netChange={overview.netChangeInPeriod}
        currentBalance={overview.currentAccountBalance}
        trend={overview.trend}
        formatAmount={formatAmount}
      />

      <BankConnectionWidget onSyncComplete={forceRefresh} />

      <div className="dashboard-grid">
        <div className="dashboard-col-left">
          <div className="dashboard-section">
            <MonthlyExpensesTrend data={expensesByMonth} />
          </div>

          <div className="dashboard-section">
            <BudgetProgressSection budgetSummary={budgetSummary} />
          </div>

          <div className="dashboard-section">
            <RecentTransactions transactions={recentTransactions} />
          </div>
        </div>

        <div className="dashboard-col-right">
          <div className="dashboard-section">
            <h3>Udgifter pr. kategori</h3>
            {drilldownCategory ? (
              <CategoryDrilldown
                category={drilldownCategory}
                totalExpenses={overview.totalExpenses}
                onBack={() => setDrilldownCategoryId(null)}
                formatAmount={formatAmount}
              />
            ) : (
              <>
                {renderChart()}
                <CategoryExpensesList
                  data={categoryDataWithPercentages}
                  totalExpenses={overview.totalExpenses}
                  formatAmount={formatAmount}
                  onSelectCategory={(item) => setDrilldownCategoryId(toDrilldownKey(item.id))}
                />
              </>
            )}
          </div>

          <div className="dashboard-section">
            <GoalProgressSection goals={goals} />
          </div>
        </div>
      </div>
    </div>
  );
}

export default DashboardOverview;
