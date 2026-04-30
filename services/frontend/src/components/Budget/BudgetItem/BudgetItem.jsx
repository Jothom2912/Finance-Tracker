// frontend/src/components/BudgetItem/BudgetItem.js

import { AlertCircle, AlertTriangle, CircleDot, CheckCircle2 } from 'lucide-react';
import './BudgetItem.css';

function BudgetItem({ 
    budget, 
    spent = 0, 
    categoryName, 
    onEdit, 
    onDelete, 
    showActions = true,
    showProgress = true,
    size = 'normal' // 'small', 'normal', 'large'
}) {
    const remaining = budget.amount - spent;
    const percentageUsed = budget.amount > 0 ? (spent / budget.amount) * 100 : 0;
    
    // Bestem status baseret på forbrug
    let status = '';
    if (remaining < 0) {
        status = 'over-budget';
    } else if (percentageUsed >= 90) {
        status = 'close-to-limit';
    } else if (percentageUsed >= 75) {
        status = 'approaching-limit';
    } else {
        status = 'within-budget';
    }

    const formatAmount = (amount) => {
        return new Intl.NumberFormat('da-DK', {
            style: 'currency',
            currency: 'DKK',
            minimumFractionDigits: 2
        }).format(amount);
    };

    const getStatusIcon = (status) => {
        // Icons are decorative: the adjacent `getStatusText()` label carries
        // the semantic meaning for screen readers, so each icon is rendered
        // with aria-hidden="true".
        switch (status) {
            case 'over-budget':
                return <AlertCircle aria-hidden="true" size={16} />;
            case 'close-to-limit':
                return <AlertTriangle aria-hidden="true" size={16} />;
            case 'approaching-limit':
                return <CircleDot aria-hidden="true" size={16} />;
            case 'within-budget':
                return <CheckCircle2 aria-hidden="true" size={16} />;
            default:
                return null;
        }
    };

    const getStatusText = (status) => {
        switch (status) {
            case 'over-budget':
                return 'Overskredet!';
            case 'close-to-limit':
                return 'Tæt på grænsen';
            case 'approaching-limit':
                return 'Nærmer sig grænsen';
            case 'within-budget':
                return 'Inden for budget';
            default:
                return '';
        }
    };

    return (
        <div className={`budget-item ${status} budget-item-${size}`}>
            <div className="budget-item-header">
                <div className="category-info">
                    <span className="status-icon">{getStatusIcon(status)}</span>
                    <span className="category-name">{categoryName}</span>
                </div>
                <span className="budget-amount">Budget: {formatAmount(budget.amount)}</span>
            </div>
            
            {showProgress && (
                <div className="budget-item-progress">
                    <div className="progress-bar-background">
                        <div 
                            className="progress-bar-fill" 
                            style={{ width: `${Math.min(100, percentageUsed)}%` }}
                        ></div>
                    </div>
                    <div className="progress-info">
                        <span className="percentage-text">{percentageUsed.toFixed(1)}% brugt</span>
                        <span className="status-text">{getStatusText(status)}</span>
                    </div>
                </div>
            )}
            
            <div className="budget-item-details">
                <div className="amount-info">
                    <span className="spent-amount">Brugt: {formatAmount(spent)}</span>
                    <span className={`remaining-amount ${remaining < 0 ? 'negative' : 'positive'}`}>
                        Resterende: {formatAmount(remaining)}
                    </span>
                </div>
            </div>

            {showActions && (onEdit || onDelete) && (
                <div className="budget-item-actions">
                    {onEdit && (
                        <button 
                            className="button secondary small-button" 
                            onClick={() => onEdit(budget)}
                        >
                            Rediger
                        </button>
                    )}
                    {onDelete && (
                        <button 
                            className="button danger small-button" 
                            onClick={() => onDelete(budget.id)}
                        >
                            Slet
                        </button>
                    )}
                </div>
            )}
        </div>
    );
}

export default BudgetItem;