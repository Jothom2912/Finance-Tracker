from typing import List, Optional, Dict, Any
from datetime import date
from backend.repository import get_budget_repository, get_category_repository, get_transaction_repository
from backend.shared.schemas.budget import BudgetCreate, BudgetUpdate, BudgetSummary, BudgetSummaryItem

# --- CRUD/Hentningsfunktioner ---

def get_budget_by_id(budget_id: int) -> Optional[Dict]:
    """Henter et specifikt budget ud fra ID."""
    repo = get_budget_repository()
    return repo.get_by_id(budget_id)

def get_budgets_by_period(account_id: int, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict]:
    """Henter budgetter for en given periode og Account ID."""
    repo = get_budget_repository()
    return repo.get_all(account_id=account_id)

def create_budget(budget: BudgetCreate) -> Dict:
    """Opretter et nyt budget."""

    if not budget.Account_idAccount:
        raise ValueError("Account ID er påkrævet for at oprette et budget.")

    # ✅ Hent category_id direkte fra objektet (det er et normalt felt)
    category_id = budget.category_id

    if not category_id:
        raise ValueError("category_id er påkrævet for at oprette et budget.")

    # Fjern felter der ikke skal i Budget tabellen
    budget_data = budget.model_dump(exclude={'month', 'year', 'category_id'})
    
    # Valider at kategorien eksisterer
    category_repo = get_category_repository()
    category = category_repo.get_by_id(category_id)
    if not category:
        raise ValueError(f"Kategori med ID {category_id} findes ikke.")

    print(f"DEBUG: category_id={category_id}, budget_data={budget_data}")

    repo = get_budget_repository()
    created_budget = repo.create(budget_data)
    
    # Note: Budget-category association håndteres i repository hvis nødvendigt
    # For nu antager vi at repositories håndterer dette korrekt
    
    print(f"DEBUG: Budget {created_budget.get('idBudget')} oprettet")
    return created_budget


def update_budget(budget_id: int, budget: BudgetUpdate) -> Optional[Dict]:
    """Opdaterer et eksisterende budget."""
    repo = get_budget_repository()
    existing = repo.get_by_id(budget_id)
    if not existing:
        return None

    update_data = budget.model_dump(exclude_unset=True)
    print(f"DEBUG update_budget: Modtaget update_data={update_data}")

    # Håndter month/year konvertering
    if 'month' in update_data or 'year' in update_data:
        month = update_data.pop('month', None)
        year = update_data.pop('year', None)
        if month and year:
            try:
                update_data['budget_date'] = date(int(year), int(month), 1).isoformat()
            except (ValueError, TypeError):
                pass

    # ✅ Hent category_id direkte fra objektet (det er et normalt felt)
    category_id = update_data.pop('category_id', None)
    print(f"DEBUG update_budget: category_id={category_id}")
    if category_id is not None:
        # Valider at kategorien eksisterer
        category_repo = get_category_repository()
        category = category_repo.get_by_id(category_id)
        if not category:
            raise ValueError(f"Kategori med ID {category_id} findes ikke.")
        # Note: Budget-category association håndteres i repository hvis nødvendigt

    return repo.update(budget_id, update_data)


def delete_budget(budget_id: int) -> bool:
    """Sletter et budget."""
    repo = get_budget_repository()
    return repo.delete(budget_id)


# --- Komplicerede logik/summary funktioner ---

def get_budget_summary(account_id: int, month: int, year: int) -> BudgetSummary:
    """Beregner en detaljeret budgetopsummering for en specifik måned/år og konto."""

    # 1. Hent budgetter, der er knyttet til den pågældende konto
    budget_repo = get_budget_repository()
    budgets = budget_repo.get_all(account_id=account_id)

    # Filtrer manuelt efter month/year hvis budget_date er sat
    filtered_budgets = []
    print(f"DEBUG: Fandt {len(budgets)} budgetter for account_id={account_id}")
    for budget in budgets:
        budget_date = budget.get("budget_date")
        if budget_date:
            if isinstance(budget_date, str):
                try:
                    from datetime import datetime
                    budget_date = datetime.fromisoformat(budget_date.replace('Z', '+00:00')).date()
                except:
                    continue
            elif hasattr(budget_date, 'date'):
                budget_date = budget_date.date()
            
            budget_month = budget_date.month
            budget_year = budget_date.year
            print(f"DEBUG: Budget {budget.get('idBudget')}: month={budget_month}, year={budget_year}, søger month={month}, year={year}")
            if budget_month == month and budget_year == year:
                filtered_budgets.append(budget)
                print(f"DEBUG: Budget {budget.get('idBudget')} matcher periode")

    print(f"DEBUG: Efter filtrering: {len(filtered_budgets)} budgetter matcher periode")
    budgets = filtered_budgets

    # 2. Hent de aggregerede udgifter for perioden (kun for denne account)
    transaction_repo = get_transaction_repository()
    # Brug get_summary_by_category hvis tilgængelig, ellers beregn manuelt
    start_date = date(year, month, 1)
    # Beregn sidste dag i måneden
    if month == 12:
        end_date = date(year + 1, 1, 1)
    else:
        end_date = date(year, month + 1, 1)
    from datetime import timedelta
    end_date = end_date - timedelta(days=1)
    
    # Hent alle transaktioner for perioden
    transactions = transaction_repo.get_all(
        start_date=start_date,
        end_date=end_date,
        account_id=account_id
    )
    
    # Aggreger udgifter (negative amounts) per kategori
    expenses_by_category: Dict[int, float] = {}
    for t in transactions:
        amount = t.get("amount", 0)
        if amount < 0:  # Udgifter er negative
            cat_id = t.get("Category_idCategory")
            if cat_id:
                expenses_by_category[cat_id] = expenses_by_category.get(cat_id, 0) + abs(float(amount))

    items: List[BudgetSummaryItem] = []
    total_budget = 0.0
    total_spent = 0.0
    over_budget_count = 0
    budget_category_ids = set()
    category_repo = get_category_repository()

    # 3. Gå gennem hvert budget og beregn status
    for budget in budgets:
        # Note: Budget-category relationship håndteres i repository
        # For nu antager vi at budget har category information hvis nødvendigt
        # Dette skal justeres baseret på hvordan repository returnerer data
        
        budget_amount = float(budget.get("amount", 0))
        
        # Hvis budget har category_id direkte, brug det
        # Ellers skal vi hente fra association table (komplekst, simplificeret her)
        # For nu antager vi at vi kan få category_id fra budget data
        category_id = budget.get("Category_idCategory")  # Hvis repository inkluderer det
        
        if category_id:
            spent = expenses_by_category.get(category_id, 0.0)
            remaining = budget_amount - spent
            percentage_used = (spent / budget_amount * 100.0) if budget_amount > 0 else 0.0

            if remaining < 0:
                over_budget_count += 1

            category = category_repo.get_by_id(category_id)
            category_name = category.get("name", "Ukendt") if category else "Ukendt"

            items.append(BudgetSummaryItem(
                category_id=category_id,
                category_name=category_name,
                budget_amount=round(budget_amount, 2),
                spent_amount=round(spent, 2),
                remaining_amount=round(remaining, 2),
                percentage_used=round(percentage_used, 2)
            ))
            total_budget += budget_amount
            total_spent += spent
            budget_category_ids.add(category_id)

    # 4. Inkluder kategorier med udgifter, men uden budget
    category_ids_with_expense = {cid for cid in expenses_by_category.keys() if cid is not None}
    missing_budget_category_ids = category_ids_with_expense - budget_category_ids

    if missing_budget_category_ids:
        for cid in missing_budget_category_ids:
            category = category_repo.get_by_id(cid)
            if category:
                spent = expenses_by_category.get(cid, 0.0)
                items.append(BudgetSummaryItem(
                    category_id=cid,
                    category_name=category.get("name", "Ukendt"),
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
