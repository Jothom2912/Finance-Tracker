import React, { useState, useEffect } from 'react';
import MessageDisplay from '../MessageDisplay';
import apiClient from '../../utils/apiClient';
import './CategoryManagement.css';

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
    const [editingCategory, setEditingCategory] = useState(null);
    const [categoryNameInput, setCategoryNameInput] = useState('');
    const [categoryTypeInput, setCategoryTypeInput] = useState('expense');

    // Lokal state til fejl/succesmeddelelser for denne komponent, hvis du vil have dem adskilt
    // Alternativt kan du bruge de setError/setSuccessMessage props direkte
    const [localError, setLocalError] = useState(null);
    const [localSuccessMessage, setLocalSuccessMessage] = useState(null);


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
            const response = editingCategory
                ? await apiClient.put(`/categories/${editingCategory.id}`, categoryData)
                : await apiClient.post('/categories/', categoryData);

            if (!response.ok) {
                const errorData = await response.json();
                const errorMessage = errorData.detail ?
                                    (Array.isArray(errorData.detail) ? errorData.detail.map(d => d.msg).join(", ") : errorData.detail)
                                    : "Ukendt fejl";
                throw new Error(errorMessage);
            }

            await response.json();

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
        if (window.confirm("Er du sikker på, at du vil slette denne kategori? Transaktioner tilknyttet vil miste deres kategori.")) {
            try {
                const response = await apiClient.delete(`/categories/${categoryId}`);

                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
                }

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
        onCloseModal(); // Lukker modalen via prop fra App.js
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
            {categories.length > 0 ? (
                <ul>
                    {categories.map(cat => (
                        <li key={cat.id}>
                            <span>
                                {cat.name} ({cat.type})
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
                        </li>
                    ))}
                </ul>
            ) : (
                <p>Ingen kategorier fundet.</p>
            )}
        </div>
    );
}

export default CategoryManagement;