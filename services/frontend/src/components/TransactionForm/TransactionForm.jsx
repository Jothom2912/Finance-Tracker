// src/components/TransactionForm/TransactionForm.js
import React, { useState, useEffect } from 'react';
import apiClient from '../../utils/apiClient';
import './TransactionForm.css';

function TransactionForm({
    categories,
    onTransactionAdded,
    transactionToEdit,
    onTransactionUpdated,
    onCancelEdit,
    setError,
    setSuccessMessage
}) {
    const [amount, setAmount] = useState('');
    const [category, setCategory] = useState('');
    const [date, setDate] = useState('');
    const [description, setDescription] = useState('');
    const [isExpense, setIsExpense] = useState(true);

    useEffect(() => {
        if (transactionToEdit) {
            setAmount(transactionToEdit.amount);
            setCategory(transactionToEdit.category_id || transactionToEdit.Category_idCategory);
            setDate(transactionToEdit.date);
            setDescription(transactionToEdit.description);
            setIsExpense(transactionToEdit.transaction_type === 'expense' || transactionToEdit.type === 'expense');
        } else {
            // Reset form for new transaction
            setAmount('');
            setCategory('');
            setDate('');
            setDescription('');
            setIsExpense(true); // Default to expense
        }
    }, [transactionToEdit]);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError(null);
        setSuccessMessage(null);

        if (!amount || !category || !date || !description) {
            setError('Alle felter skal udfyldes.');
            return;
        }

        // Backend forventer negativt beløb for expenses, positivt for income
        const amountValue = parseFloat(amount);
        const finalAmount = isExpense ? -Math.abs(amountValue) : Math.abs(amountValue);

        // Valider at kategori er valgt
        if (!category || category === '') {
            setError('Vælg venligst en kategori.');
            return;
        }

        const categoryId = parseInt(category);
        if (isNaN(categoryId)) {
            setError('Ugyldig kategori valgt.');
            return;
        }

        const transactionData = {
            amount: finalAmount,
            category_id: categoryId,
            transaction_date: date,
            description: description,
            type: isExpense ? 'expense' : 'income'
        };

        try {
            console.log('📤 Sender transaktion data:', transactionData);
            const transactionId = transactionToEdit?.idTransaction || transactionToEdit?.id;
            const response = transactionToEdit
                ? await apiClient.put(`/transactions/${transactionId}`, transactionData)
                : await apiClient.post('/transactions/', transactionData);

            if (!response.ok) {
                const errorData = await response.json();
                console.error('❌ Backend fejl:', errorData);
                const errorMessage = Array.isArray(errorData.detail)
                    ? errorData.detail.map(e => e.msg || JSON.stringify(e)).join(', ')
                    : errorData.detail || `HTTP error! status: ${response.status}`;
                throw new Error(errorMessage);
            }

            if (transactionToEdit) {
                onTransactionUpdated();
            } else {
                onTransactionAdded();
            }
            setSuccessMessage(transactionToEdit ? 'Transaktion opdateret!' : 'Transaktion tilføjet!');
        } catch (err) {
            console.error("Fejl ved håndtering af transaktion:", err);
            setError(`Fejl: ${err.message}`);
        }
    };

    return (
        <div className="transaction-form-container" data-cy="transaction-form"> {/* Ny container klasse for formularen */}
            <h3>{transactionToEdit ? 'Rediger Transaktion' : 'Tilføj Ny Transaktion'}</h3>
            <form onSubmit={handleSubmit}>
                <div className="form-group"> {/* Generel gruppe for input felter */}
                    <label htmlFor="amount">Beløb:</label>
                    <input
                        type="number"
                        id="amount"
                        data-cy="transaction-amount"
                        value={amount}
                        onChange={(e) => setAmount(e.target.value)}
                        required
                    />
                </div>

                <div className="form-group">
                    <label htmlFor="category">Kategori:</label>
                    <select
                        id="category"
                        data-cy="transaction-category"
                        value={category}
                        onChange={(e) => setCategory(e.target.value)}
                        required
                    >
                        <option key="default" value="">Vælg Kategori</option>
                        {categories.map((cat) => (
                            <option key={cat.id || cat.idCategory} value={cat.id || cat.idCategory}>
                                {cat.name}
                            </option>
                        ))}
                    </select>
                </div>

                <div className="form-group">
                    <label htmlFor="date">Dato:</label>
                    <input
                        type="date"
                        id="date"
                        data-cy="transaction-date"
                        value={date}
                        onChange={(e) => setDate(e.target.value)}
                        required
                    />
                </div>

                <div className="form-group">
                    <label htmlFor="description">Beskrivelse:</label>
                    <input
                        type="text"
                        id="description"
                        data-cy="transaction-description"
                        value={description}
                        onChange={(e) => setDescription(e.target.value)}
                        required
                    />
                </div>

                <div className="form-group radio-group"> {/* Specifik klasse for radio knapper */}
                    <label>
                        <input
                            type="radio"
                            value="expense"
                            data-cy="transaction-type-expense"
                            checked={isExpense}
                            onChange={() => setIsExpense(true)}
                        />
                        Udgift
                    </label>
                    <label>
                        <input
                            type="radio"
                            value="income"
                            data-cy="transaction-type-income"
                            checked={!isExpense}
                            onChange={() => setIsExpense(false)}
                        />
                        Indkomst
                    </label>
                </div>

                <div className="form-actions"> {/* Gruppe for formular knapper */}
                    <button type="submit" className="button" data-cy="submit-transaction">
                        {transactionToEdit ? 'Opdater Transaktion' : 'Tilføj Transaktion'}
                    </button>
                    {transactionToEdit && (
                        <button type="button" className="button secondary" onClick={onCancelEdit}>
                            Annuller Redigering
                        </button>
                    )}
                </div>
            </form>
        </div>
    );
}

export default TransactionForm;