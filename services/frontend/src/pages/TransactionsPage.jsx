import { useState, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import TransactionForm from '../components/TransactionForm/TransactionForm';
import TransactionsList from '../components/TransactionsList/TransactionsList';
import FilterComponent from '../components/FilterComponent/FilterComponent';
import Modal from '../components/Modal/Modal';
import Pagination from '../components/Pagination/Pagination';

import { useCategories } from '../hooks/useCategories';
import { useAllSubcategories } from '../hooks/useSubcategories';
import { useTransactions } from '../hooks/useTransactions';
import { useTransactionSearch } from '../hooks/useTransactionSearch';
import { useDebouncedValue } from '../hooks/useDebouncedValue';
import { useNotifications } from '../hooks/useNotifications';
import { useConfirm } from '../components/ConfirmDialog/ConfirmDialog';
import { formatLocalISODate } from '../lib/formatters';
import { pageCountOf } from '../lib/pagination';
import { BANK_FORMAT_OPTIONS, CSV_MAX_BYTES } from '../lib/bankFormats';

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

  // Fritekstsøgning (dansk stemming via analytics-læsesiden). Aktiv
  // søgning erstatter den filtrerede liste; tom søgning = uændret side.
  const [searchTerm, setSearchTerm] = useState('');
  const debouncedSearchTerm = useDebouncedValue(searchTerm);

  const [page, setPage] = useState(1);

  // Ét udtryk over ALT der ændrer hvilket resultatsæt vi ser på. Dermed
  // dækkes FilterComponents datopresets automatisk, og et sjette filter
  // tilføjet senere kommer med af sig selv — hvor det at pakke de enkelte
  // settere ind ville misse det i tavshed.
  const resultsKey = `${filterStartDate}|${filterEndDate}|${selectedCategory}|${debouncedSearchTerm}`;
  const [lastResultsKey, setLastResultsKey] = useState(resultsKey);

  // Nulstilling UNDER render, ikke i en useEffect: med en effekt har den
  // render der går FORUD for effekten allerede de nye filtre og det gamle
  // sidetal, så et request med skip=100 mod et friskfiltreret sæt bliver
  // sendt og kortvarigt vist, før nulstillingen lander.
  let effectivePage = page;
  if (resultsKey !== lastResultsKey) {
    setLastResultsKey(resultsKey);
    setPage(1);
    effectivePage = 1;
  }

  // Søgningen kaldes FØR listen, fordi listen gates på isSearchActive (se
  // nedenfor). Rækkefølgen er den eneste kobling mellem de to — begge kaldes
  // ubetinget, så hook-rækkefølgen er stabil.
  //
  // filters MED: søgningen respekterer det aktive datofilter — panelet stod
  // synligt aktivt og blev ignoreret. Bemærk adfærdsændringen: default-filtret
  // er den aktuelle måned, så søgning dækker nu kun den. Global søgning hører i
  // en eksplicit "søg i hele historikken"-toggle, ikke her.
  // Sidetallet DELES med listen: de to resultatsæt er gensidigt udelukkende
  // (isSearchActive skifter både overskrift og array), der er én pager, og
  // debouncedSearchTerm ligger i resultsKey, så søgning ind/ud/ændret nulstiller
  // til side 1. Et separat searchPage skulle have egne nulstillingsregler og
  // ville genopvække et forældet sidetal når brugeren skrev samme ord igen.
  const {
    isSearchActive,
    results: searchResults,
    totalCount: searchTotalCount,
    isPaging: searchIsPaging,
    loading: searchLoading,
    error: searchError,
  } = useTransactionSearch(debouncedSearchTerm, filters, effectivePage);

  // enabled: !isSearchActive — mens en søgning er aktiv vises søgeresultaterne,
  // og listens svar bliver kastet væk. Uden gaten koster hvert sideklik under
  // søgning et ubrugt REST-request. Mutationerne (create/update/remove/uploadCsv)
  // er upåvirkede: kun queryen pauses, så gem og CSV-upload virker under søgning.
  const {
    transactions,
    totalCount,
    isPaging,
    loading: txLoading,
    error: txError,
    create: createTx,
    update: updateTx,
    remove: removeTx,
    uploadCsv,
  } = useTransactions(filters, effectivePage, { enabled: !isSearchActive });

  // Én pager over to populationer — hver med sin egen total. Listens total må
  // ikke stå over søgeresultater og omvendt.
  const activeTotalCount = isSearchActive ? searchTotalCount : totalCount;
  const activeIsPaging = isSearchActive ? searchIsPaging : isPaging;
  const pageCount = activeTotalCount != null ? pageCountOf(activeTotalCount) : null;

  // Totalen kan krympe under os (slet sidste række på side 2). Betinget af at
  // serveren HAR svaret — deraf null-kontrakten på totalCount — og konvergerer
  // i ét skridt fordi pageCountOf bunder i 1. Bevidst ikke gjort i mutationens
  // onSuccess: dér kender klienten ikke den nye total før refetchen lander.
  // Kan ikke kollidere med nulstillingen ovenfor: efter den er effectivePage 1,
  // og 1 > pageCount er umuligt.
  if (pageCount != null && effectivePage > pageCount) {
    setPage(pageCount);
    effectivePage = pageCount;
  }

  // Persistens for formularen — mutation-hook'et ejer invalideringen,
  // så handleTransactionSaved kun lukker modal + toaster.
  const handleSaveTransaction = useCallback(
    (id, data) => (id ? updateTx({ id, data }) : createTx(data)),
    [createTx, updateTx],
  );

  const handleTransactionSaved = useCallback((isEdit) => {
    setShowFormModal(false);
    setTransactionToEdit(null);
    // Til side 1, så den nye/rettede række faktisk er på skærmen. Rækkefølgen
    // er date DESC, så en ny transaktion lander øverst — altså på side 1.
    setPage(1);
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
    // Pre-flight (P2-29): serveren afviser også, men først når hele filen er
    // sendt — og apiClient timer ud efter 30s. At fange det her sparer
    // brugeren ventetiden; serveren er stadig den der håndhæver.
    if (csvFile.size > CSV_MAX_BYTES) {
      const limitMb = Math.round(CSV_MAX_BYTES / (1024 * 1024));
      showError(`Filen er for stor (grænsen er ${limitMb} MB). Del den op i flere mindre importer.`);
      return;
    }

    setUploadingCsv(true);
    clearMessages();
    try {
      const result = await uploadCsv({ file: csvFile, bankFormat });
      // Samme grund som ved gem: de importerede rækker skal være synlige.
      setPage(1);
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
        {/*
          Kun totalen her; rækkeintervallet ligger i pageren. Den gamle tekst
          "50 af 400 resultater" meldte en afkortning brugeren ikke kunne gøre
          noget ved. Samme dæmpning som tabellen, fordi keepPreviousData kort
          viser det forrige søgeords tal ved siden af det nye ord.
        */}
        {isSearchActive && !searchLoading && !searchError && searchTotalCount != null && (
          <p className={`transaction-search-status${searchIsPaging ? ' is-stale' : ''}`}>
            {searchTotalCount} resultater for “{debouncedSearchTerm}”
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
          <>
            {/*
              Sideskift DÆMPER den gamle tabel i stedet for at erstatte den med
              en spinner: en spinner ville kollapse sidens højde og scroll-hoppe
              brugeren. prefers-reduced-motion i index.css neutraliserer allerede
              transitionen globalt.
            */}
            <div
              className={`transactions-results${activeIsPaging ? ' is-stale' : ''}`}
              aria-busy={activeIsPaging}
            >
              <TransactionsList
                transactions={isSearchActive ? searchResults : transactions}
                onEdit={handleEditTransaction}
                onDelete={handleDeleteTransaction}
                onCreateTransaction={() => { setShowFormModal(true); clearMessages(); }}
                onQuickCategorize={handleQuickCategorize}
                categories={categories}
                allSubcategories={allSubcategories}
                // En tom søgning er ikke tom "for de valgte filtre", og et CTA
                // om at oprette sin FØRSTE transaktion er forkert når listen
                // udenfor søgningen er fuld af rækker.
                emptyMessage={
                  isSearchActive
                    ? `Ingen transaktioner matcher “${debouncedSearchTerm}”.`
                    : 'Ingen transaktioner fundet for de valgte filtre.'
                }
                showEmptyAction={!isSearchActive}
              />
            </div>
            <Pagination
              page={effectivePage}
              totalCount={activeTotalCount}
              onPageChange={setPage}
            />
          </>
        )}
      </div>
    </div>
  );
}

export default TransactionsPage;
