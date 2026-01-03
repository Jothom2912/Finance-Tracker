from backend.repositories import get_budget_repository, get_category_repository, get_transaction_repository
from typing import List, Optional, Dict, Any

from backend.shared.schemas.budget import BudgetCreate, BudgetUpdate, BudgetSummary, BudgetSummaryItem

def _get_category_expenses_for_period( month: int, year: int, account_id: int) -> Dict[int, float]:
    """Henter aggregerede udgifter for hver kategori for en given måned og år."""
    repo = get_transaction_repository()
    return repo.get_expenses_by_category_for_period(month, year, account_id)


# --- CRUD/Hentningsfunktioner ---

def get_budget_by_id(budget_id: int) -> Optional[Dict]:
    """Henter et specifikt budget ud fra ID."""
    repo = get_budget_repository()
    return repo.get_by_id(budget_id)

def get_budgets_by_period( account_id: int, start_date: str, end_date: str) -> List[dict]:
    """Henter budgetter for en given periode og Account ID (juster dette baseret på din Budget model)."""
    repo = get_budget_repository()
    return repo.get_all(account_id, start_date, end_date)

def create_budget( budget: BudgetCreate) -> Dict:
    """Opretter et nyt budget."""
    repo = get_budget_repository()
    if not budget.Account_idAccount:
        raise ValueError("Account ID er påkrævet for at oprette et budget.")

    # ✅ Hent category_id direkte fra objektet (det er et normalt felt)
    category_id = budget.category_id

    if not category_id:
        raise ValueError("category_id er påkrævet for at oprette et budget.")

    # Fjern felter der ikke skal i Budget tabellen, men behold category_id for association
    budget_data = budget.model_dump(exclude={'month', 'year'})

    print(f"DEBUG: category_id={category_id}, budget_data={budget_data}")

    # Create budget with category association via repository
    result = repo.create(budget_data)
    return result

def update_budget( budget_id: int, budget: BudgetUpdate) -> Optional[Dict]:
    """Opdaterer et eksisterende budget."""
    repo = get_budget_repository()
    
    update_data = budget.model_dump(exclude_unset=True)
    print(f"DEBUG update_budget: Modtaget update_data={update_data}")

    # Håndter month/year konvertering
    if 'month' in update_data or 'year' in update_data:
        month = update_data.pop('month', None)
        year = update_data.pop('year', None)
        if month and year:
            try:
                from datetime import date
                update_data['budget_date'] = date(int(year), int(month), 1)
            except (ValueError, TypeError):
                pass

    # category_id is now handled by the repository
    print(f"DEBUG update_budget: category_id={update_data.get('category_id')}")

    # Update budget via repository (includes category association)
    result = repo.update(budget_id, update_data)
    return result

def delete_budget( budget_id: int) -> bool:
    """Sletter et budget."""
    repo = get_budget_repository()
    return repo.delete(budget_id)


# --- Komplicerede logik/summary funktioner ---

def get_budget_summary(account_id: int, month: int, year: int) -> BudgetSummary:
    """Beregner en detaljeret budgetopsummering for en specifik måned/år og konto."""

    # 1. Hent budgetter, der er knyttet til den pågældende konto og dækker perioden
    repo = get_budget_repository()

    budgets_data = repo.get_all(account_id=account_id)
    
    # Filtrer manuelt efter month/year hvis budget_date er sat
    filtered_budgets = []
    print(f"DEBUG: Fandt {len(budgets_data)} budgetter for account_id={account_id}")
    for budget in budgets_data:
        print(f"DEBUG: Budget {budget['idBudget']}: amount={budget['amount']}, budget_date={budget.get('budget_date')}, categories count={len(budget.get('categories', []))}")
        if budget.get('budget_date'):
            budget_month = budget['budget_date'].month if hasattr(budget['budget_date'], 'month') else int(str(budget['budget_date'])[:7].split('-')[1])
            budget_year = budget['budget_date'].year if hasattr(budget['budget_date'], 'year') else int(str(budget['budget_date'])[:4])
            print(f"DEBUG: Budget {budget['idBudget']}: month={budget_month}, year={budget_year}, søger month={month}, year={year}")
            if budget_month == month and budget_year == year:
                filtered_budgets.append(budget)
                print(f"DEBUG: Budget {budget['idBudget']} matcher periode")
        # Hvis budget_date er None, inkluder det ikke (kræver budget_date for at matche periode)

    print(f"DEBUG: Efter filtrering: {len(filtered_budgets)} budgetter matcher periode")
    budgets_data = filtered_budgets

    # 2. Hent de aggregerede udgifter for perioden (kun for denne account)
    expenses_by_category = _get_category_expenses_for_period(month, year, account_id)

    items: List[BudgetSummaryItem] = []
    total_budget = 0.0
    total_spent = 0.0
    over_budget_count = 0
    budget_category_ids = set()

    # 3. Gå gennem hvert budget og beregn status
    for budget in budgets_data:
        relevant_categories = budget.get("categories", [])
        print(f"DEBUG: Budget {budget['idBudget']}: relevant_categories count={len(relevant_categories)}")

        for category in relevant_categories:
            # Tjek for duplikat for at undgå at behandle samme kategori to gange (hvis flere budgetter peger på samme kategori)
            if category["idCategory"] in budget_category_ids:
                continue
            budget_category_ids.add(category["idCategory"])

            spent = expenses_by_category.get(category["idCategory"], 0.0)
            remaining = float(budget["amount"]) - spent
            percentage_used = (spent / float(budget["amount"]) * 100.0) if float(budget["amount"]) > 0 else 0.0

            if remaining < 0:
                over_budget_count += 1

            items.append(BudgetSummaryItem(
                category_id=category["idCategory"],
                category_name=category["name"],
                budget_amount=round(float(budget["amount"]), 2),
                spent_amount=round(spent, 2),
                remaining_amount=round(remaining, 2),
                percentage_used=round(percentage_used, 2)
            ))
            total_budget += float(budget["amount"])
            total_spent += spent

    # 4. Inkluder kategorier med udgifter, men uden budget
    category_ids_with_expense = {cid for cid in expenses_by_category.keys() if cid is not None}
    missing_budget_category_ids = category_ids_with_expense - budget_category_ids

    if missing_budget_category_ids:
        # Get category names from repository
        category_repo = get_category_repository()
        categories_data = []
        for cid in missing_budget_category_ids:
            cat_data = category_repo.get_by_id(cid)
            if cat_data:
                categories_data.append(cat_data)
        
        id_to_name = {cat["idCategory"]: cat["name"] for cat in categories_data}

        for cid in missing_budget_category_ids:
            spent = expenses_by_category.get(cid, 0.0)
            items.append(BudgetSummaryItem(
                category_id=cid,
                category_name=id_to_name.get(cid, "Ukendt"),
                budget_amount=0.0,
                spent_amount=round(spent, 2),
                remaining_amount=round(-spent, 2),
                percentage_used=100.0
            ))
            total_spent += spent

    total_remaining = total_budget - total_spent

    return BudgetSummary(
        month=f"{month:02d}",
        year=str(year),
        items=items,
        total_budget=round(total_budget, 2),
        total_spent=round(total_spent, 2),
        total_remaining=round(total_remaining, 2),
        over_budget_count=over_budget_count
    )
