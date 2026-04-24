import React, { useState, useCallback, useMemo, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { BarChart3 } from 'lucide-react';
import CategoryFilterPanel from '../components/CategoryFilterPanel/CategoryFilterPanel';
import CategorySpendingOverview from '../components/CategorySpendingOverview/CategorySpendingOverview';
import CategoryManagement from '../components/CategoryManagement/CategoryManagement';
import Modal from '../components/Modal/Modal';
import { useCategories } from '../hooks/useCategories';
import { useNotifications } from '../hooks/useNotifications';
import { fetchDashboardOverview } from '../api/dashboard';
import { fetchBudgetSummary } from '../api/budgets';
import './CategoriesPage.css';

function CategoriesPage() {
  const { categories, refresh: refreshCategories } = useCategories();
  const { showError, showSuccess, clearMessages } = useNotifications();
  const [showManagementModal, setShowManagementModal] = useState(false);

  const now = new Date();
  const [selectedMonth, setSelectedMonth] = useState(
    () => String(now.getMonth() + 1).padStart(2, '0'),
  );
  const [selectedYear, setSelectedYear] = useState(() => String(now.getFullYear()));
  const [typeFilter, setTypeFilter] = useState('expense');
  const [selectedCategoryIds, setSelectedCategoryIds] = useState([]);

  const [overviewData, setOverviewData] = useState(null);
  const [budgetData, setBudgetData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [dataError, setDataError] = useState(null);

  const hasAccount = Boolean(localStorage.getItem('account_id'));

  const dateRange = useMemo(() => {
    const month = parseInt(selectedMonth, 10);
    const year = parseInt(selectedYear, 10);
    const startDate = `${year}-${String(month).padStart(2, '0')}-01`;
    const lastDay = new Date(year, month, 0).getDate();
    const endDate = `${year}-${String(month).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`;
    return { startDate, endDate, month, year };
  }, [selectedMonth, selectedYear]);

  const fetchData = useCallback(async () => {
    if (!hasAccount) {
      setLoading(false);
      setDataError('no-account');
      return;
    }

    setLoading(true);
    setDataError(null);
    try {
      const [overview, budget] = await Promise.all([
        fetchDashboardOverview({
          startDate: dateRange.startDate,
          endDate: dateRange.endDate,
        }),
        fetchBudgetSummary({
          month: dateRange.month,
          year: dateRange.year,
        }),
      ]);
      setOverviewData(overview);
      setBudgetData(budget);
    } catch (err) {
      console.error('Fejl ved hentning af kategori-data:', err);
      const isAccountError = err.message?.toLowerCase().includes('account')
        || err.status === 400;
      if (isAccountError) {
        setDataError('no-account');
      } else {
        setDataError('fetch-error');
        showError(err.message || 'Kunne ikke hente data.');
      }
    } finally {
      setLoading(false);
    }
  }, [dateRange, showError, hasAccount]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleCategoryChange = useCallback(() => {
    refreshCategories();
    fetchData();
    showSuccess('Handling udført!');
    setShowManagementModal(false);
  }, [refreshCategories, fetchData, showSuccess]);

  return (
    <div className="categories-page">
      <div className="categories-page-header">
        <h2>Kategorioverblik</h2>
        <button
          className="manage-categories-btn"
          data-cy="manage-categories-btn"
          onClick={() => { setShowManagementModal(true); clearMessages(); }}
        >
          Administrer kategorier
        </button>
      </div>

      <CategoryFilterPanel
        selectedMonth={selectedMonth}
        setSelectedMonth={setSelectedMonth}
        selectedYear={selectedYear}
        setSelectedYear={setSelectedYear}
        categories={categories}
        selectedCategoryIds={selectedCategoryIds}
        setSelectedCategoryIds={setSelectedCategoryIds}
        typeFilter={typeFilter}
        setTypeFilter={setTypeFilter}
      />

      {dataError === 'no-account' ? (
        <div className="categories-no-account" data-cy="no-account-state">
          <div className="no-account-icon"><BarChart3 aria-hidden="true" size={48} /></div>
          <h3>Ingen konto valgt</h3>
          <p>Vælg en konto for at se dit kategori-overblik med forbrug og budgetter.</p>
          <Link to="/account-selector" className="select-account-btn">
            Vælg konto
          </Link>
        </div>
      ) : (
        <CategorySpendingOverview
          expensesByCategory={overviewData?.expenses_by_category}
          budgetSummary={budgetData}
          selectedCategoryIds={selectedCategoryIds}
          categories={categories}
          loading={loading}
        />
      )}

      <Modal
        isOpen={showManagementModal}
        onClose={() => setShowManagementModal(false)}
        title="Administrer kategorier"
      >
        <CategoryManagement
          categories={categories}
          onCategoryAdded={handleCategoryChange}
          onCategoryUpdated={handleCategoryChange}
          onCategoryDeleted={handleCategoryChange}
          setError={showError}
          setSuccessMessage={showSuccess}
        />
      </Modal>
    </div>
  );
}

export default CategoriesPage;
