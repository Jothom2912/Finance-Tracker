import { useState, useEffect, useMemo } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import MessageDisplay from '../MessageDisplay';
import { createCategory, updateCategory, deleteCategory as apiDeleteCategory } from '../../api/categories';
import { useConfirm } from '../ConfirmDialog/ConfirmDialog';
import SubcategoryList from './SubcategoryList';
import './CategoryManagement.css';

const TYPE_LABELS = {
  expense: 'Udgift',
  income: 'Indtægt',
  transfer: 'Overførsel',
};

// Ændret props: Fjernet 'fetchCategories', 'error', 'successMessage'
// Tilføjet 'onCategoryAdded', 'onCategoryUpdated', 'onCategoryDeleted'
function CategoryManagement({
    categories,
    onCategoryAdded,    // <--- NY PROP: Kaldes ved tilføjelse
    onCategoryUpdated,  // <--- NY PROP: Kaldes ved opdatering
    onCategoryDeleted,  // <--- NY PROP: Kaldes ved sletning
    setError,           // Bruger stadig disse til at sætte fejl/succes i App.js
    setSuccessMessage,  // Bruger stadig disse til at sætte fejl/succes i App.js
    onCloseModal        // Til at lukke modalen
}) {
    const confirm = useConfirm();
    const [editingCategory, setEditingCategory] = useState(null);
    const [categoryNameInput, setCategoryNameInput] = useState('');
    const [categoryTypeInput, setCategoryTypeInput] = useState('expense');
    const [expandedCategoryId, setExpandedCategoryId] = useState(null);

    // Lokal state til fejl/succesmeddelelser for denne komponent, hvis du vil have dem adskilt
    // Alternativt kan du bruge de setError/setSuccessMessage props direkte
    const [localError, setLocalError] = useState(null);
    const [localSuccessMessage, setLocalSuccessMessage] = useState(null);

    // display_order kommer fra taksonomien (categorization-service);
    // navne-fallback for brugeroprettede kategorier uden ordering.
    const sortedCategories = useMemo(
        () => [...categories].sort(
            (a, b) => (a.display_order ?? 0) - (b.display_order ?? 0) || a.name.localeCompare(b.name, 'da'),
        ),
        [categories],
    );


    useEffect(() => {
        if (editingCategory) {
            setCategoryNameInput(editingCategory.name);
            setCategoryTypeInput(editingCategory.type);
        } else {
            setCategoryNameInput('');
            setCategoryTypeInput('expense');
        }
        // Nulstil fejl/succesmeddelelser ved skift af redigeringstilstand
        setLocalError(null);
        setLocalSuccessMessage(null);
        setError(null); // Nulstil også i App.js
        setSuccessMessage(null); // Nulstil også i App.js
    }, [editingCategory, setError, setSuccessMessage]);

    const handleSubmitCategory = async (e) => {
        e.preventDefault();
        setLocalError(null);
        setLocalSuccessMessage(null);
        setError(null);
        setSuccessMessage(null);

        if (!categoryNameInput) {
            setLocalError('Kategorinavn må ikke være tomt.');
            return;
        }

        const categoryData = {
            name: categoryNameInput,
            type: categoryTypeInput
        };

        try {
            if (editingCategory) {
                await updateCategory(editingCategory.id, categoryData);
            } else {
                await createCategory(categoryData);
            }

            setLocalSuccessMessage(editingCategory ? 'Kategori opdateret!' : 'Kategori oprettet!');
            setSuccessMessage(editingCategory ? 'Kategori opdateret!' : 'Kategori oprettet!'); // Send besked til App.js

            setCategoryNameInput('');
            setCategoryTypeInput('expense');
            setEditingCategory(null);

            // Nøgleændring her: Kald den relevante prop fra App.js
            if (editingCategory) {
                onCategoryUpdated(); // Kalder handleCategoryChange i App.js
            } else {
                onCategoryAdded(); // Kalder handleCategoryChange i App.js
            }

        } catch (err) {
            console.error("Fejl ved håndtering af kategori:", err);
            setLocalError(err.message || "Der opstod en uventet fejl.");
            setError(err.message || "Der opstod en uventet fejl."); // Send fejl til App.js
            setLocalSuccessMessage(null);
            setSuccessMessage(null);
        }
    };

    const handleDeleteCategory = async (categoryId) => {
        const ok = await confirm({
            title: 'Slet kategori?',
            message: 'Transaktioner tilknyttet kategorien mister deres kategori. Handlingen kan ikke fortrydes.',
            confirmLabel: 'Slet',
            variant: 'danger',
        });
        if (!ok) return;

        try {
            await apiDeleteCategory(categoryId);

            setLocalSuccessMessage('Kategori slettet!');
            setSuccessMessage('Kategori slettet!'); // Send besked til App.js
            setLocalError(null);
            setError(null);

            // Nøgleændring her: Kald den relevante prop fra App.js
            onCategoryDeleted(); // Kalder handleCategoryChange i App.js

        } catch (err) {
            console.error("Fejl ved sletning af kategori:", err);
            setLocalError(err.message || "Der opstod en uventet fejl ved sletning.");
            setError(err.message || "Der opstod en uventet fejl ved sletning."); // Send fejl til App.js
            setLocalSuccessMessage(null);
            setSuccessMessage(null);
        }
    };

    const handleCancelCategoryEdit = () => {
        setEditingCategory(null);
        setCategoryNameInput('');
        setCategoryTypeInput('expense');
        setLocalError(null);
        setLocalSuccessMessage(null);
        setError(null);
        setSuccessMessage(null);
        onCloseModal?.(); // Lukker modalen via prop fra App.js
    };

    return (
        <div className="category-management-container">
            {/* Brug lokal MessageDisplay til fejl/succes inde i modalen */}
            <MessageDisplay message={localError} type="error" />
            <MessageDisplay message={localSuccessMessage} type="success" />

            <form onSubmit={handleSubmitCategory}>
                <div>
                    <label>
                        Kategorinavn:
                        <input
                            type="text"
                            value={categoryNameInput}
                            onChange={(e) => setCategoryNameInput(e.target.value)}
                            required
                        />
                    </label>
                </div>
                <div>
                    <label>
                        Type:
                        <select value={categoryTypeInput} onChange={(e) => setCategoryTypeInput(e.target.value)}>
                            <option value="expense">Udgift</option>
                            <option value="income">Indtægt</option>
                            <option value="transfer">Overførsel</option>
                        </select>
                    </label>
                </div>
                <button type="submit">{editingCategory ? 'Opdater Kategori' : 'Opret Kategori'}</button>
                {editingCategory && (
                    <button type="button" onClick={handleCancelCategoryEdit} style={{ marginLeft: '10px', backgroundColor: '#555' }}>
                        Annuller
                    </button>
                )}
            </form>

            <h3>Eksisterende Kategorier:</h3>
            {sortedCategories.length > 0 ? (
                <ul className="category-management-list">
                    {sortedCategories.map(cat => {
                        const isExpanded = expandedCategoryId === cat.id;
                        return (
                            <li key={cat.id} className="category-management-item">
                                <div className="category-row">
                                    <button
                                        type="button"
                                        className="expand-button"
                                        onClick={() => setExpandedCategoryId(isExpanded ? null : cat.id)}
                                        aria-expanded={isExpanded}
                                        title={isExpanded ? 'Skjul underkategorier' : 'Vis underkategorier'}
                                    >
                                        {isExpanded
                                            ? <ChevronDown size={16} aria-hidden="true" />
                                            : <ChevronRight size={16} aria-hidden="true" />}
                                    </button>
                                    <span className="category-row-name">
                                        {cat.name}
                                        <span className={`type-badge type-${cat.type}`}>
                                            {TYPE_LABELS[cat.type] ?? cat.type}
                                        </span>
                                    </span>
                                    <div className="category-actions">
                                        <button
                                            onClick={() => setEditingCategory(cat)}
                                            className="edit-button"
                                        >
                                            Rediger
                                        </button>
                                        <button
                                            onClick={() => handleDeleteCategory(cat.id)}
                                            className="delete-button"
                                        >
                                            Slet
                                        </button>
                                    </div>
                                </div>
                                {isExpanded && (
                                    <SubcategoryList
                                        categoryId={cat.id}
                                        onError={(msg) => { setLocalError(msg); setError(msg); }}
                                        onSuccess={(msg) => { setLocalSuccessMessage(msg); }}
                                    />
                                )}
                            </li>
                        );
                    })}
                </ul>
            ) : (
                <p>Ingen kategorier fundet.</p>
            )}
        </div>
    );
}

export default CategoryManagement;