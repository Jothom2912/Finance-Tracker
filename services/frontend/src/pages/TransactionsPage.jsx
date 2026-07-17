import { useState, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import TransactionForm from '../components/TransactionForm/TransactionForm';
import TransactionsList from '../components/TransactionsList/TransactionsList';
import FilterComponent from '../components/FilterComponent/FilterComponent';
import Modal from '../components/Modal/Modal';

import { useCategories } from '../hooks/useCategories';
import { useAllSubcategories } from '../hooks/useSubcategories';
import { useTransactions } from '../hooks/useTransactions';
import { useTransactionSearch } from '../hooks/useTransactionSearch';
import { useDebouncedValue } from '../hooks/useDebouncedValue';
import { useNotifications } from '../hooks/useNotifications';
import { useConfirm } from '../components/ConfirmDialog/ConfirmDialog';
import { formatLocalISODate } from '../lib/formatters';
import { BANK_FORMAT_OPTIONS } from '../lib/bankFormats';

import '../components/FilterComponent/FilterComponent.css';
import './TransactionsPage.css';

function TransactionsPage() {
  const navigate = useNavigate();
  const {
    categories,
    loading: categoriesLoading,
    error: categoriesError,
    refresh: refreshCategories,
  } = useCategories();
  const { subcategories: allSubcategories } = useAllSubcategories();
  const { showError, showSuccess, clearMessages } = useNotifications();
  const confirm = useConfirm();

  const [transactionToEdit, setTransactionToEdit] = useState(null);
  const [showFormModal, setShowFormModal] = useState(false);

  const [filterStartDate, setFilterStartDate] = useState(() => {
    const d = new Date();
    return formatLocalISODate(new Date(d.getFullYear(), d.getMonth(), 1));
  });
  const [filterEndDate, setFilterEndDate] = useState(() => {
    const d = new Date();
    return formatLocalISODate(new Date(d.getFullYear(), d.getMonth() + 1, 0));
  });
  const [selectedCategory, setSelectedCategory] = useState('');

  const [csvFile, setCsvFile] = useState(null);
  const [uploadingCsv, setUploadingCsv] = useState(false);
  const [bankFormat, setBankFormat] = useState('internal');

  const filters = useMemo(
    () => ({
      startDate: filterStartDate,
      endDate: filterEndDate,
      categoryId: selectedCategory,
    }),
    [filterStartDate, filterEndDate, selectedCategory],
  );

  const {
    transactions,
    loading: txLoading,
    error: txError,
    create: createTx,
    update: updateTx,
    remove: removeTx,
    uploadCsv,
  } = useTransactions(filters);

  // Fritekstsøgning (dansk stemming via analytics-læsesiden). Aktiv
  // søgning erstatter den filtrerede liste; tom søgning = uændret side.
  const [searchTerm, setSearchTerm] = useState('');
  const debouncedSearchTerm = useDebouncedValue(searchTerm);
  const {
    isSearchActive,
    results: searchResults,
    totalCount: searchTotalCount,
    loading: searchLoading,
    error: searchError,
  } = useTransactionSearch(debouncedSearchTerm);

  // Persistens for formularen — mutation-hook'et ejer invalideringen,
  // så handleTransactionSaved kun lukker modal + toaster.
  const handleSaveTransaction = useCallback(
    (id, data) => (id ? updateTx({ id, data }) : createTx(data)),
    [createTx, updateTx],
  );

  const handleTransactionSaved = useCallback((isEdit) => {
    setShowFormModal(false);
    setTransactionToEdit(null);
    showSuccess(isEdit ? 'Transaktion opdateret!' : 'Transaktion tilføjet!');
  }, [showSuccess]);

  // Inline-rettelse fra listen: samme update-mutation som modal-flowet,
  // så tier=manual + feedback-loopet trigges server-side.
  const handleQuickCategorize = useCallback(async (transaction, categorization) => {
    try {
      await updateTx({ id: transaction.id, data: categorization });
      showSuccess(
        categorization.subcategory_id
          ? 'Kategori rettet — systemet husker det til fremtidige transaktioner.'
          : 'Kategori rettet.',
      );
    } catch (err) {
      showError(`Kunne ikke rette kategori: ${err.message}`);
    }
  }, [updateTx, showSuccess, showError]);

  const handleCreateRuleFromTransaction = useCallback((prefill) => {
    navigate('/rules', { state: { prefill } });
  }, [navigate]);

  const handleEditTransaction = useCallback((transaction) => {
    setTransactionToEdit(transaction);
    setShowFormModal(true);
    clearMessages();
  }, [clearMessages]);

  const handleCancelEdit = useCallback(() => {
    setTransactionToEdit(null);
    setShowFormModal(false);
    clearMessages();
  }, [clearMessages]);

  const handleDeleteTransaction = useCallback(async (transactionId) => {
    const ok = await confirm({
      title: 'Slet transaktion?',
      message: 'Transaktionen slettes permanent og kan ikke gendannes.',
      confirmLabel: 'Slet',
      variant: 'danger',
    });
    if (!ok) return;
    try {
      await removeTx(transactionId);
      showSuccess('Transaktion slettet!');
    } catch (err) {
      showError(`Fejl ved sletning: ${err.message}`);
    }
  }, [confirm, removeTx, showSuccess, showError]);

  const handleCsvUpload = useCallback(async (e) => {
    e.preventDefault();
    if (!csvFile) { showError('Vælg en CSV fil først.'); return; }

    setUploadingCsv(true);
    clearMessages();
    try {
      const result = await uploadCsv({ file: csvFile, bankFormat });
      showSuccess(result.message || `CSV uploadet! ${result.imported_count || ''} transaktioner importeret.`);
    } catch (err) {
      showError(err.message || 'Fejl ved CSV upload.');
    } finally {
      setUploadingCsv(false);
      setCsvFile(null);
      const fileInput = document.querySelector('.csv-upload-section input[type="file"]');
      if (fileInput) fileInput.value = '';
    }
  }, [csvFile, bankFormat, uploadCsv, showError, showSuccess, clearMessages]);

  const getCurrentPeriodLabel = () => {
    if (!filterStartDate || !filterEndDate) return 'valgt periode';
    const start = new Date(filterStartDate);
    const end = new Date(filterEndDate);
    const months = [
      'Januar', 'Februar', 'Marts', 'April', 'Maj', 'Juni',
      'Juli', 'August', 'September', 'Oktober', 'November', 'December',
    ];
    if (start.getMonth() === end.getMonth() && start.getFullYear() === end.getFullYear()) {
      return `${months[start.getMonth()]} ${start.getFullYear()}`;
    }
    return `${start.toLocaleDateString('da-DK')} - ${end.toLocaleDateString('da-DK')}`;
  };

  return (
    <div className="transactions-page-container">
      <div className="transactions-page-header">
        <div className="header-content">
          <h1>Transaktioner</h1>
          <p className="header-subtitle">Administrer dine indtægter og udgifter</p>
        </div>
      </div>

      <div className="transaction-search-section">
        <label htmlFor="transaction-search" className="visually-hidden">
          Søg i transaktioner
        </label>
        <input
          id="transaction-search"
          type="search"
          className="transaction-search-input"
          placeholder="Søg i transaktioner (fx 'netto' eller 'forsikring')…"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
        {isSearchActive && !searchLoading && !searchError && (
          <p className="transaction-search-status">
            {searchResults.length} af {searchTotalCount} resultater for “{debouncedSearchTerm}”
          </p>
        )}
      </div>

      <div className="controls-section">
        <div className="filter-wrapper">
          <FilterComponent
            filterStartDate={filterStartDate}
            setFilterStartDate={setFilterStartDate}
            filterEndDate={filterEndDate}
            setFilterEndDate={setFilterEndDate}
            selectedCategory={selectedCategory}
            setSelectedCategory={setSelectedCategory}
            categories={categories}
            categoriesLoading={categoriesLoading}
            categoriesError={categoriesError}
            onRetryCategories={refreshCategories}
          />
        </div>
      </div>

      <div className="csv-upload-section">
        <h3>Upload transaktioner (CSV)</h3>
        <form onSubmit={handleCsvUpload} className="csv-upload-form">
          <div className="file-input-group">
            <select
              value={bankFormat}
              onChange={(e) => setBankFormat(e.target.value)}
              className="bank-format-select"
              disabled={uploadingCsv}
            >
              {BANK_FORMAT_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
            <input
              type="file"
              accept=".csv"
              onChange={(e) => setCsvFile(e.target.files[0])}
              disabled={uploadingCsv}
            />
            <button
              type="submit"
              disabled={!csvFile || uploadingCsv}
              className="upload-button"
            >
              {uploadingCsv ? 'Uploader...' : 'Upload CSV'}
            </button>
          </div>
          <p className="upload-info">Upload CSV fil med transaktioner for {getCurrentPeriodLabel()}</p>
        </form>
      </div>

      <div className="action-buttons">
        <button
          className="add-transaction-button"
          onClick={() => { setShowFormModal(true); clearMessages(); }}
        >
          <span className="button-icon">+</span>
          <span className="button-label">Tilføj ny transaktion</span>
        </button>
      </div>

      {showFormModal && (
        <Modal
          isOpen={showFormModal}
          onClose={handleCancelEdit}
          title={transactionToEdit ? 'Rediger transaktion' : 'Ny transaktion'}
        >
          <TransactionForm
            categories={categories}
            categoriesLoading={categoriesLoading}
            categoriesError={categoriesError}
            onRetryCategories={refreshCategories}
            onSave={handleSaveTransaction}
            onTransactionAdded={() => handleTransactionSaved(false)}
            transactionToEdit={transactionToEdit}
            onTransactionUpdated={() => handleTransactionSaved(true)}
            onCancelEdit={handleCancelEdit}
            onCreateRule={handleCreateRuleFromTransaction}
            setError={showError}
          />
        </Modal>
      )}

      <div className="transactions-content">
        <h3>{isSearchActive ? 'Søgeresultater' : 'Alle Transaktioner'}</h3>
        {(isSearchActive ? searchLoading : txLoading) ? (
          <p>Indlæser transaktioner...</p>
        ) : (isSearchActive ? searchError : txError) ? (
          <p className="message-display error">Fejl: {isSearchActive ? searchError : txError}</p>
        ) : (
          <TransactionsList
            transactions={isSearchActive ? searchResults : transactions}
            onEdit={handleEditTransaction}
            onDelete={handleDeleteTransaction}
            onCreateTransaction={() => { setShowFormModal(true); clearMessages(); }}
            onQuickCategorize={handleQuickCategorize}
            categories={categories}
            allSubcategories={allSubcategories}
          />
        )}
      </div>
    </div>
  );
}

export default TransactionsPage;
