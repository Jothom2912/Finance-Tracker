import React, { useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import CategoryPieChart from '../../Charts/PieChart';
import SummaryCards from '../SummaryCards/SummaryCards';
import CategoryExpensesList from '../CategoryExpensesList/CategoryExpensesList';
import BudgetProgressSection from '../BudgetProgressSection/BudgetProgressSection';
import GoalProgressSection from '../GoalProgressSection/GoalProgressSection';
import RecentTransactions from '../RecentTransactions/RecentTransactions';
import BankConnectionWidget from '../BankConnectionWidget/BankConnectionWidget';
import MonthlyExpensesTrend from '../MonthlyExpensesTrend/MonthlyExpensesTrend';
import { useDashboardData } from '../../hooks/useDashboardData/useDashboardData';
import { getMonthLabel } from '../../lib/formatters';
import './DashboardOverview.css';

function DashboardOverview() {
  const queryClient = useQueryClient();
  const forceRefresh = useCallback(
    () => queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
    [queryClient],
  );

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
  } = useDashboardData();

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

  const now = new Date();
  const monthLabel = getMonthLabel(String(now.getMonth() + 1).padStart(2, '0'));
  const yearLabel = now.getFullYear();

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
        />
      </div>
    );
  };

  return (
    <div className="dashboard-overview-container">
      <div className="dashboard-header">
        <h2 className="dashboard-title">
          {monthLabel} {yearLabel}
        </h2>
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
            {renderChart()}
            <CategoryExpensesList
              data={categoryDataWithPercentages}
              totalExpenses={overview.totalExpenses}
              formatAmount={formatAmount}
            />
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
