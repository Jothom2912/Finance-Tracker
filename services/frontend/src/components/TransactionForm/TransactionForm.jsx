import React, { useState, useEffect } from 'react';
import { createTransaction as apiCreateTransaction, updateTransaction as apiUpdateTransaction } from '../../api/transactions';
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

        // Backend kræver positivt beløb (>= 0.01). Retningen (income vs. expense)
        // kodes af transaction_type-enum'en, ikke af fortegnet på beløbet.
        const amountValue = parseFloat(amount);
        const finalAmount = Math.abs(amountValue);

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

        const selectedCategory = categories.find((cat) => (cat.id || cat.idCategory) === categoryId);

        const transactionData = {
            amount: finalAmount,
            category_id: categoryId,
            category_name: selectedCategory?.name || null,
            date: date,
            description: description,
            type: isExpense ? 'expense' : 'income',
        };

        try {
            const transactionId = transactionToEdit?.idTransaction || transactionToEdit?.id;
            if (transactionToEdit) {
                await apiUpdateTransaction(transactionId, transactionData);
                onTransactionUpdated();
            } else {
                await apiCreateTransaction(transactionData);
                onTransactionAdded();
            }
            setSuccessMessage(transactionToEdit ? 'Transaktion opdateret!' : 'Transaktion tilføjet!');
        } catch (err) {
            setError(`Fejl: ${err.message}`);
        }
    };

    return (
        <div className="transaction-form-container">
            <h3>{transactionToEdit ? 'Rediger Transaktion' : 'Tilføj Ny Transaktion'}</h3>
            <form onSubmit={handleSubmit}>
                <div className="form-group"> {/* Generel gruppe for input felter */}
                    <label htmlFor="amount">Beløb:</label>
                    <input
                        type="number"
                        id="amount"
                        value={amount}
                        onChange={(e) => setAmount(e.target.value)}
                        required
                    />
                </div>

                <div className="form-group">
                    <label htmlFor="category">Kategori:</label>
                    <select
                        id="category"
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
                            checked={isExpense}
                            onChange={() => setIsExpense(true)}
                        />
                        Udgift
                    </label>
                    <label>
                        <input
                            type="radio"
                            value="income"
                            checked={!isExpense}
                            onChange={() => setIsExpense(false)}
                        />
                        Indkomst
                    </label>
                </div>

                <div className="form-actions"> {/* Gruppe for formular knapper */}
                    <button type="submit" className="button">
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