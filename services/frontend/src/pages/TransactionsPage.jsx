import { useState, useCallback, useMemo } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import TransactionForm from '../components/TransactionForm/TransactionForm';
import TransactionsList from '../components/TransactionsList/TransactionsList';
import FilterComponent from '../components/FilterComponent/FilterComponent';
import Modal from '../components/Modal/Modal';

import { useCategories } from '../hooks/useCategories';
import { useTransactions } from '../hooks/useTransactions';
import { useNotifications } from '../hooks/useNotifications';
import { useConfirm } from '../components/ConfirmDialog/ConfirmDialog';
import { formatLocalISODate } from '../lib/formatters';

import '../components/FilterComponent/FilterComponent.css';
import './TransactionsPage.css';

function TransactionsPage() {
  const queryClient = useQueryClient();
  const { categories } = useCategories();
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
    remove: removeTx,
    uploadCsv,
  } = useTransactions(filters);

  const invalidateTransactionViews = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['transactions'] });
    queryClient.invalidateQueries({ queryKey: ['dashboard'] });
  }, [queryClient]);

  const handleTransactionSaved = useCallback((isEdit) => {
    setShowFormModal(false);
    setTransactionToEdit(null);
    invalidateTransactionViews();
    showSuccess(isEdit ? 'Transaktion opdateret!' : 'Transaktion tilføjet!');
  }, [invalidateTransactionViews, showSuccess]);

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
      const result = await uploadCsv(csvFile);
      showSuccess(result.message || `CSV uploadet! ${result.imported_count || ''} transaktioner importeret.`);
    } catch (err) {
      showError(err.message || 'Fejl ved CSV upload.');
    } finally {
      setUploadingCsv(false);
      setCsvFile(null);
      const fileInput = document.querySelector('.csv-upload-section input[type="file"]');
      if (fileInput) fileInput.value = '';
    }
  }, [csvFile, uploadCsv, showError, showSuccess, clearMessages]);

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
          />
        </div>
      </div>

      <div className="csv-upload-section">
        <h3>Upload transaktioner (CSV)</h3>
        <form onSubmit={handleCsvUpload} className="csv-upload-form">
          <div className="file-input-group">
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
            onTransactionAdded={() => handleTransactionSaved(false)}
            transactionToEdit={transactionToEdit}
            onTransactionUpdated={() => handleTransactionSaved(true)}
            onCancelEdit={handleCancelEdit}
            setError={showError}
            setSuccessMessage={showSuccess}
          />
        </Modal>
      )}

      <div className="transactions-content">
        <h3>Alle Transaktioner</h3>
        {txLoading ? (
          <p>Indlæser transaktioner...</p>
        ) : txError ? (
          <p className="message-display error">Fejl: {txError}</p>
        ) : (
          <TransactionsList
            transactions={transactions}
            onEdit={handleEditTransaction}
            onDelete={handleDeleteTransaction}
            onCreateTransaction={() => { setShowFormModal(true); clearMessages(); }}
            categories={categories}
          />
        )}
      </div>
    </div>
  );
}

export default TransactionsPage;
