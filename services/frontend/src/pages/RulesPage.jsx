import { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useRules } from '../hooks/useRules';
import { useCategories } from '../hooks/useCategories';
import { useSubcategories } from '../hooks/useSubcategories';
import { useNotifications } from '../hooks/useNotifications';
import { useConfirm } from '../components/ConfirmDialog/ConfirmDialog';
import './RulesPage.css';

/**
 * F1-02: brugerdefinerede kategoriseringsregler.
 *
 * To sektioner: "Dine regler" (keyword-regler, fuld CRUD) og "Lært af
 * dine rettelser" (auto-oprettede merchant-regler fra feedback-loopet —
 * kun slet, så brugeren kan tilbagekalde hvad systemet har lært).
 *
 * Kan prefilles via navigation-state fra "Opret regel fra denne
 * transaktion": { prefill: { pattern_value, category_id, subcategory_id } }.
 */
function RulesPage() {
  const { rules, loading, error, create, update, remove, isSaving } = useRules();
  const { categories } = useCategories();
  const { showError, showSuccess } = useNotifications();
  const confirm = useConfirm();
  const location = useLocation();
  const navigate = useNavigate();

  const [editingRule, setEditingRule] = useState(null);
  const [patternValue, setPatternValue] = useState('');
  const [categoryId, setCategoryId] = useState('');
  const [subcategoryId, setSubcategoryId] = useState('');
  const [showForm, setShowForm] = useState(false);

  const { subcategories, loading: subcategoriesLoading } = useSubcategories(
    categoryId ? parseInt(categoryId, 10) : null,
  );

  // Prefill fra transaktions-genvejen — brug én gang, ryd så state så
  // refresh/back ikke genåbner formularen.
  useEffect(() => {
    const prefill = location.state?.prefill;
    if (!prefill) return;
    setPatternValue(prefill.pattern_value || '');
    setCategoryId(prefill.category_id ? String(prefill.category_id) : '');
    setSubcategoryId(prefill.subcategory_id ? String(prefill.subcategory_id) : '');
    setShowForm(true);
    navigate(location.pathname, { replace: true, state: null });
  }, [location, navigate]);

  const userRules = useMemo(() => rules.filter((r) => !r.is_learned), [rules]);
  const learnedRules = useMemo(() => rules.filter((r) => r.is_learned), [rules]);

  const resetForm = () => {
    setEditingRule(null);
    setPatternValue('');
    setCategoryId('');
    setSubcategoryId('');
    setShowForm(false);
  };

  const startEdit = (rule) => {
    setEditingRule(rule);
    setPatternValue(rule.pattern_value);
    setCategoryId(rule.category_id ? String(rule.category_id) : '');
    setSubcategoryId(String(rule.subcategory_id));
    setShowForm(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (patternValue.trim().length < 2) {
      showError('Nøgleordet skal være mindst 2 tegn.');
      return;
    }
    if (!subcategoryId) {
      showError('Vælg en underkategori som reglen skal ramme.');
      return;
    }
    try {
      if (editingRule) {
        await update({
          id: editingRule.id,
          data: { pattern_value: patternValue.trim(), subcategory_id: parseInt(subcategoryId, 10) },
        });
        showSuccess('Regel opdateret.');
      } else {
        await create({ pattern_value: patternValue.trim(), subcategory_id: parseInt(subcategoryId, 10) });
        showSuccess('Regel oprettet — den anvendes på fremtidige transaktioner.');
      }
      resetForm();
    } catch (err) {
      showError(err.message || 'Kunne ikke gemme reglen.');
    }
  };

  const handleToggleActive = async (rule) => {
    try {
      await update({ id: rule.id, data: { active: !rule.active } });
      showSuccess(rule.active ? 'Regel deaktiveret.' : 'Regel aktiveret.');
    } catch (err) {
      showError(err.message || 'Kunne ikke opdatere reglen.');
    }
  };

  const handleDelete = async (rule) => {
    const ok = await confirm({
      title: rule.is_learned ? 'Glem denne lærte regel?' : 'Slet regel?',
      message: rule.is_learned
        ? `Systemet glemmer at "${rule.pattern_value}" hører til ${rule.subcategory_name}. Du kan lære den igen ved at rette en transaktion.`
        : `Reglen for "${rule.pattern_value}" slettes permanent.`,
      confirmLabel: rule.is_learned ? 'Glem' : 'Slet',
      variant: 'danger',
    });
    if (!ok) return;
    try {
      await remove(rule.id);
      showSuccess(rule.is_learned ? 'Lært regel glemt.' : 'Regel slettet.');
    } catch (err) {
      showError(err.message || 'Kunne ikke slette reglen.');
    }
  };

  const targetLabel = (rule) =>
    rule.category_name ? `${rule.category_name} › ${rule.subcategory_name}` : rule.subcategory_name;

  return (
    <div className="rules-page">
      <div className="rules-page-header">
        <div>
          <h1>Regler</h1>
          <p className="header-subtitle">
            Styr hvordan dine transaktioner kategoriseres automatisk
          </p>
        </div>
        {!showForm && (
          <button className="button" onClick={() => setShowForm(true)}>
            + Ny regel
          </button>
        )}
      </div>

      {showForm && (
        <form className="rule-form" onSubmit={handleSubmit}>
          <h3>{editingRule ? 'Rediger regel' : 'Ny regel'}</h3>
          <p className="rule-form-hint">
            Når beskrivelsen indeholder nøgleordet, kategoriseres transaktionen automatisk.
          </p>
          <div className="rule-form-fields">
            <div className="form-group">
              <label htmlFor="rule-pattern">Beskrivelsen indeholder:</label>
              <input
                id="rule-pattern"
                type="text"
                value={patternValue}
                onChange={(e) => setPatternValue(e.target.value)}
                placeholder='fx "netto" eller "fitness world"'
                required
              />
            </div>
            <div className="form-group">
              <label htmlFor="rule-category">Kategori:</label>
              <select
                id="rule-category"
                value={categoryId}
                onChange={(e) => {
                  setCategoryId(e.target.value);
                  setSubcategoryId('');
                }}
                required
              >
                <option value="">Vælg kategori</option>
                {categories.map((cat) => (
                  <option key={cat.id} value={cat.id}>{cat.name}</option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label htmlFor="rule-subcategory">Underkategori:</label>
              <select
                id="rule-subcategory"
                value={subcategoryId}
                onChange={(e) => setSubcategoryId(e.target.value)}
                disabled={!categoryId || subcategoriesLoading}
                required
              >
                <option value="">
                  {!categoryId
                    ? 'Vælg først kategori'
                    : subcategoriesLoading
                      ? 'Indlæser…'
                      : 'Vælg underkategori'}
                </option>
                {subcategories.map((sub) => (
                  <option key={sub.id} value={sub.id}>{sub.name}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="form-actions">
            <button type="submit" className="button" disabled={isSaving}>
              {isSaving ? 'Gemmer…' : editingRule ? 'Gem ændringer' : 'Opret regel'}
            </button>
            <button type="button" className="button secondary" onClick={resetForm}>
              Annuller
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <p>Indlæser regler…</p>
      ) : error ? (
        <p className="message-display error">Fejl: {error}</p>
      ) : (
        <>
          <section className="rules-section" aria-label="Dine regler">
            <h2>Dine regler</h2>
            {userRules.length === 0 ? (
              <p className="rules-empty">
                Ingen regler endnu. Opret en regel, eller ret kategorien på en
                transaktion — så lærer systemet det selv.
              </p>
            ) : (
              <table className="rules-table">
                <thead>
                  <tr>
                    <th>Nøgleord</th>
                    <th>Kategoriseres som</th>
                    <th>Status</th>
                    <th>Handlinger</th>
                  </tr>
                </thead>
                <tbody>
                  {userRules.map((rule) => (
                    <tr key={rule.id} className={rule.active ? '' : 'rule-inactive'}>
                      <td data-label="Nøgleord">&quot;{rule.pattern_value}&quot;</td>
                      <td data-label="Kategoriseres som">{targetLabel(rule)}</td>
                      <td data-label="Status">{rule.active ? 'Aktiv' : 'Deaktiveret'}</td>
                      <td data-label="Handlinger" className="rule-actions">
                        <button className="button secondary small-button" onClick={() => startEdit(rule)}>
                          Rediger
                        </button>
                        <button className="button secondary small-button" onClick={() => handleToggleActive(rule)}>
                          {rule.active ? 'Deaktivér' : 'Aktivér'}
                        </button>
                        <button className="button danger small-button" onClick={() => handleDelete(rule)}>
                          Slet
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <section className="rules-section" aria-label="Lært af dine rettelser">
            <h2>Lært af dine rettelser</h2>
            <p className="rules-section-hint">
              Når du retter kategorien på en transaktion, husker systemet det og
              anvender det automatisk på fremtidige transaktioner fra samme sted.
            </p>
            {learnedRules.length === 0 ? (
              <p className="rules-empty">
                Intet lært endnu — ret kategorien på en transaktion for at komme i gang.
              </p>
            ) : (
              <table className="rules-table">
                <thead>
                  <tr>
                    <th>Genkendt tekst</th>
                    <th>Kategoriseres som</th>
                    <th>Handlinger</th>
                  </tr>
                </thead>
                <tbody>
                  {learnedRules.map((rule) => (
                    <tr key={rule.id}>
                      <td data-label="Genkendt tekst">&quot;{rule.pattern_value}&quot;</td>
                      <td data-label="Kategoriseres som">{targetLabel(rule)}</td>
                      <td data-label="Handlinger" className="rule-actions">
                        <button className="button danger small-button" onClick={() => handleDelete(rule)}>
                          Glem
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </>
      )}
    </div>
  );
}

export default RulesPage;
