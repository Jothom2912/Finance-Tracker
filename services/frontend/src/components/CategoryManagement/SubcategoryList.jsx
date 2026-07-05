import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useSubcategories, subcategoriesQueryKey } from '../../hooks/useSubcategories';
import {
  createSubcategory,
  updateSubcategory,
  deleteSubcategory,
} from '../../api/subcategories';
import { useConfirm } from '../ConfirmDialog/ConfirmDialog';

/**
 * Inline-administration af én kategoris underkategorier.
 * Lazy: henter først når kategorien er foldet ud (mountes af parent).
 * Backend-guards (refereret af merchants/regler, fallback 'Anden')
 * svarer 409 — fejlbeskeden vises direkte.
 */
function SubcategoryList({ categoryId, onError, onSuccess }) {
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const { subcategories, loading, error } = useSubcategories(categoryId);

  const [newName, setNewName] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [editingName, setEditingName] = useState('');
  const [busy, setBusy] = useState(false);

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: subcategoriesQueryKey(categoryId) });
  };

  const run = async (fn, successMessage) => {
    setBusy(true);
    try {
      await fn();
      invalidate();
      onSuccess?.(successMessage);
    } catch (err) {
      onError?.(err.message || 'Der opstod en uventet fejl.');
    } finally {
      setBusy(false);
    }
  };

  const handleAdd = async (e) => {
    e.preventDefault();
    const name = newName.trim();
    if (!name) return;
    await run(async () => {
      await createSubcategory(categoryId, { name });
      setNewName('');
    }, 'Underkategori oprettet!');
  };

  const handleRename = async (subcategoryId) => {
    const name = editingName.trim();
    if (!name) return;
    await run(async () => {
      await updateSubcategory(subcategoryId, { name });
      setEditingId(null);
      setEditingName('');
    }, 'Underkategori omdøbt!');
  };

  const handleDelete = async (sub) => {
    const ok = await confirm({
      title: 'Slet underkategori?',
      message: `"${sub.name}" slettes. Transaktioner beholder deres viste navn, men kan ikke længere vælge den.`,
      confirmLabel: 'Slet',
      variant: 'danger',
    });
    if (!ok) return;
    await run(() => deleteSubcategory(sub.id), 'Underkategori slettet!');
  };

  if (loading) return <p className="subcategory-status">Indlæser underkategorier…</p>;
  if (error) return <p className="subcategory-status error">{error}</p>;

  return (
    <div className="subcategory-list">
      {subcategories.length === 0 ? (
        <p className="subcategory-status">Ingen underkategorier endnu.</p>
      ) : (
        <ul>
          {subcategories.map((sub) => (
            <li key={sub.id} className="subcategory-item">
              {editingId === sub.id ? (
                <form
                  className="subcategory-edit-form"
                  onSubmit={(e) => { e.preventDefault(); handleRename(sub.id); }}
                >
                  <input
                    type="text"
                    value={editingName}
                    onChange={(e) => setEditingName(e.target.value)}
                    autoFocus
                    disabled={busy}
                  />
                  <button type="submit" className="edit-button" disabled={busy}>Gem</button>
                  <button
                    type="button"
                    className="delete-button"
                    onClick={() => { setEditingId(null); setEditingName(''); }}
                    disabled={busy}
                  >
                    Annuller
                  </button>
                </form>
              ) : (
                <>
                  <span className="subcategory-name">
                    {sub.name}
                    {sub.is_default && <span className="subcategory-default-tag">standard</span>}
                  </span>
                  <div className="category-actions">
                    <button
                      className="edit-button"
                      onClick={() => { setEditingId(sub.id); setEditingName(sub.name); }}
                      disabled={busy}
                    >
                      Omdøb
                    </button>
                    <button
                      className="delete-button"
                      onClick={() => handleDelete(sub)}
                      disabled={busy}
                    >
                      Slet
                    </button>
                  </div>
                </>
              )}
            </li>
          ))}
        </ul>
      )}

      <form className="subcategory-add-form" onSubmit={handleAdd}>
        <input
          type="text"
          placeholder="+ Tilføj underkategori"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          disabled={busy}
        />
        <button type="submit" disabled={busy || !newName.trim()}>Tilføj</button>
      </form>
    </div>
  );
}

export default SubcategoryList;
