import { useState, useCallback, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { BarChart3 } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import CategoryFilterPanel from '../components/CategoryFilterPanel/CategoryFilterPanel';
import CategorySpendingOverview from '../components/CategorySpendingOverview/CategorySpendingOverview';
import CategoryManagement from '../components/CategoryManagement/CategoryManagement';
import Modal from '../components/Modal/Modal';
import { useCategories } from '../hooks/useCategories';
import { useNotifications } from '../hooks/useNotifications';
import { usePeriodOverview } from '../hooks/usePeriodOverview';
import { invalidateFinancialData } from '../lib/invalidateFinancialData';
import './CategoriesPage.css';

function CategoriesPage() {
  const queryClient = useQueryClient();
  const { categories } = useCategories();
  const { showError, showSuccess, clearMessages } = useNotifications();
  const [showManagementModal, setShowManagementModal] = useState(false);

  const now = new Date();
  const [selectedMonth, setSelectedMonth] = useState(
    () => String(now.getMonth() + 1).padStart(2, '0'),
  );
  const [selectedYear, setSelectedYear] = useState(() => String(now.getFullYear()));
  const [typeFilter, setTypeFilter] = useState('expense');
  const [selectedCategoryIds, setSelectedCategoryIds] = useState([]);

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

  const handleCategoryChange = useCallback(() => {
    invalidateFinancialData(queryClient, { scope: 'categories' });
    showSuccess('Handling udført!');
    setShowManagementModal(false);
  }, [queryClient, showSuccess]);

  const noAccount = !hasAccount;

  return (
    <div className="categories-page">
      <div className="categories-page-header">
        <h2>Kategorioverblik</h2>
        <button
          className="manage-categories-btn"
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
          selectedCategoryIds={selectedCategoryIds}
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
          onCloseModal={() => setShowManagementModal(false)}
        />
      </Modal>
    </div>
  );
}

export default CategoriesPage;
