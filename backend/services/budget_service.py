from typing import List, Optional, Dict, Any
from datetime import date
from sqlalchemy.orm import Session
from backend.repositories import get_budget_repository, get_category_repository, get_transaction_repository
from backend.shared.schemas.budget import BudgetCreate, BudgetUpdate, BudgetSummary, BudgetSummaryItem

# --- CRUD/Hentningsfunktioner ---

def get_budget_by_id(budget_id: int, db: Session) -> Optional[Dict]:
    """Henter et specifikt budget ud fra ID."""
    repo = get_budget_repository(db)
    return repo.get_by_id(budget_id)

def get_budgets_by_period(account_id: int, db: Session, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict]:
    """Henter budgetter for en given periode og Account ID."""
    repo = get_budget_repository(db)
    return repo.get_all(account_id=account_id)

def create_budget(budget: BudgetCreate, db: Session) -> Dict:
    """Opretter et nyt budget."""

    if not budget.Account_idAccount:
        raise ValueError("Account ID er påkrævet for at oprette et budget.")

    # ✅ Hent category_id direkte fra objektet (det er et normalt felt)
    category_id = budget.category_id

    if not category_id:
        raise ValueError("category_id er påkrævet for at oprette et budget.")

    # Fjern felter der ikke skal i Budget tabellen
    budget_data = budget.model_dump(exclude={'month', 'year', 'category_id'})
    
    # ✅ FIX: Tilføj Category_idCategory til budget_data så repository kan oprette association
    budget_data['Category_idCategory'] = category_id
    
    # Valider at kategorien eksisterer
    category_repo = get_category_repository(db)
    category = category_repo.get_by_id(category_id)
    if not category:
        raise ValueError(f"Kategori med ID {category_id} findes ikke.")

    print(f"DEBUG: category_id={category_id}, budget_data={budget_data}")

    repo = get_budget_repository(db)
    created_budget = repo.create(budget_data)
    
    # Note: Budget-category association håndteres i repository hvis nødvendigt
    # For nu antager vi at repositories håndterer dette korrekt
    
    print(f"DEBUG: Budget {created_budget.get('idBudget')} oprettet")
    return created_budget


def update_budget(budget_id: int, budget: BudgetUpdate, db: Session) -> Optional[Dict]:
    """Opdaterer et eksisterende budget."""
    repo = get_budget_repository(db)
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
        category_repo = get_category_repository(db)
        category = category_repo.get_by_id(category_id)
        if not category:
            raise ValueError(f"Kategori med ID {category_id} findes ikke.")
        # Note: Budget-category association håndteres i repository hvis nødvendigt
        update_data['Category_idCategory'] = category_id

    return repo.update(budget_id, update_data)


def delete_budget(budget_id: int, db: Session) -> bool:
    """Sletter et budget."""
    repo = get_budget_repository(db)
    return repo.delete(budget_id)


# --- Komplicerede logik/summary funktioner ---

def get_budget_summary(account_id: int, month: int, year: int, db: Session) -> BudgetSummary:
    """Beregner en detaljeret budgetopsummering for en specifik måned/år og konto."""

    # 1. Hent budgetter, der er knyttet til den pågældende konto
    budget_repo = get_budget_repository(db)
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
    
    # ✅ DEBUG: Log alle budgets med deres amounts
    print(f"DEBUG get_budget_summary: Fandt {len(budgets)} budgets")
    for b in budgets:
        print(f"DEBUG budget: id={b.get('idBudget')}, category_id={b.get('Category_idCategory')}, amount={b.get('amount')}, type={type(b.get('amount'))}")

    # 2. Hent de aggregerede udgifter for perioden (kun for denne account)
    transaction_repo = get_transaction_repository(db)
    # Beregn start/slut dato for måneden
    from calendar import monthrange
    start_date = date(year, month, 1)
    _, last_day = monthrange(year, month)
    end_date = date(year, month, last_day)
    
    # Hent alle transaktioner for perioden
    transactions = transaction_repo.get_all(
        start_date=start_date,
        end_date=end_date,
        account_id=account_id
    )
    
    print(f"DEBUG get_budget_summary: Fandt {len(transactions)} transaktioner")
    
    # ✅ Aggreger udgifter per kategori - brug type field i stedet for amount < 0
    expenses_by_category: Dict[int, float] = {}
    for t in transactions:
        amount = float(t.get("amount", 0))
        tx_type = t.get("type", "")
        # ✅ Brug type field for at identificere expenses
        if tx_type == "expense" or (tx_type == "" and amount < 0):
            cat_id = t.get("Category_idCategory")
            if cat_id:
                # ✅ For expenses, brug absolut værdi
                expenses_by_category[cat_id] = expenses_by_category.get(cat_id, 0) + abs(amount)
    
    print(f"DEBUG spent_by_category: {expenses_by_category}")

    items: List[BudgetSummaryItem] = []
    total_budget = 0.0
    total_spent = 0.0
    over_budget_count = 0
    budget_category_ids = set()
    category_repo = get_category_repository(db)
    
    # ✅ FIX: Opret budget lookup dictionary
    budget_by_category: Dict[int, float] = {}
    for budget in budgets:
        cat_id = budget.get("Category_idCategory")
        # ✅ KRITISK: Hent amount fra budget - tjek om det er None eller 0
        amount = budget.get("amount")
        if amount is None:
            print(f"⚠️ WARNING: Budget {budget.get('idBudget')} har None amount!")
            amount = 0.0
        else:
            amount = float(amount)
        budget_by_category[cat_id] = amount
        print(f"DEBUG: Mapping category {cat_id} -> budget {amount}")

    # 3. ✅ FIX: Gå gennem hvert budget og beregn status
    for budget in budgets:
        category_id = budget.get("Category_idCategory")
        
        if not category_id:
            print(f"⚠️ WARNING: Budget {budget.get('idBudget')} mangler Category_idCategory")
            continue
        
        # ✅ FIX: Brug budget amount direkte fra budget_by_category
        budget_amount = budget_by_category.get(category_id, 0.0)
        
        if budget_amount == 0.0:
            # ✅ Double-check om amount faktisk er 0 eller om det er en fejl
            raw_amount = budget.get("amount")
            print(f"DEBUG: Budget {budget.get('idBudget')} har amount={raw_amount} (type={type(raw_amount)})")
            if raw_amount is not None:
                budget_amount = float(raw_amount)
                budget_by_category[category_id] = budget_amount
        
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
            budget_amount=round(budget_amount, 2),  # ✅ Skal være fra budget, ikke 0
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
