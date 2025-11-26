from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, extract
from sqlalchemy.exc import IntegrityError
from typing import List, Optional, Dict, Any

from ..models.budget import Budget as BudgetModel # Antag at du bruger alias for at undgå navnekollision
from ..models.category import Category as CategoryModel
from ..models.transaction import Transaction as TransactionModel
from ..schemas.budget import BudgetCreate, BudgetUpdate, BudgetSummary, BudgetSummaryItem

# --- Hjælpefunktioner ---

def _get_category_expenses_for_period(db: Session, month: int, year: int) -> Dict[int, float]:
    """Henter aggregerede udgifter for hver kategori for en given måned og år."""
    
    # Filtrer for at sikre, at vi kun tager udgifter (amount < 0)
    # Aggreger efter Category_idCategory
    expenses_by_category = db.query(
        TransactionModel.Category_idCategory.label('category_id'),
        func.sum(TransactionModel.amount).label('total_spent')
    ).filter(
        extract('month', TransactionModel.date) == month,
        extract('year', TransactionModel.date) == year,
        TransactionModel.amount < 0 # Udgifter er negative
    ).group_by(
        TransactionModel.Category_idCategory
    ).all()

    # Returnerer resultatet som {category_id: total_spent} (positivt tal for udgift)
    return {row.category_id: abs(float(row.total_spent)) for row in expenses_by_category if row.category_id is not None}


# --- CRUD/Hentningsfunktioner ---

def get_budget_by_id(db: Session, budget_id: int):
    """Henter et specifikt budget ud fra ID."""
    return db.query(BudgetModel).options(
        joinedload(BudgetModel.categories)
    ).filter(
        BudgetModel.idBudget == budget_id
    ).first()

def get_budgets_by_period(db: Session, account_id: int, start_date: str, end_date: str) -> List[BudgetModel]:
    """Henter budgetter for en given periode og Account ID (juster dette baseret på din Budget model)."""
    
    # Bemærk: Din Budget-model i den gamle kode havde 'month' og 'year',
    # men Budget-modellen fra din nye SQLAlchemy-struktur har kun `budget_date`.
    # Jeg antager, at du enten filtrerer på `budget_date` eller på den konto, de er knyttet til.
    # Jeg bruger her en generisk tilgang til at hente alt for en konto.
    
    query = db.query(BudgetModel).options(
        joinedload(BudgetModel.categories) # Inkluderer relaterede kategorier
    ).filter(
        BudgetModel.Account_idAccount == account_id # Filtrer på Account ID
        # Hvis du vil filtrere på dato: BudgetModel.budget_date.between(start_date, end_date)
    )
    
    return query.all()

def create_budget(db: Session, budget: BudgetCreate) -> BudgetModel:
    """Opretter et nyt budget."""
    
    # Træk de relaterede Category IDs ud
    category_ids = budget.category_ids
    budget_data = budget.model_dump(exclude={"category_ids"})

    # Tjek for duplikat (Hvis du har en unik kombination af dato/konto/kategori, skal dette tjekkes)
    # Dette kræver en klar definition af unikhed i Budget-modellen, da Budget nu har mange-til-mange med Category.
    # Vi ignorerer duplikat-tjekket her for at fokusere på servicestrukturen.
    
    db_budget = BudgetModel(**budget_data)
    
    # Hent Category objekter
    categories = db.query(CategoryModel).filter(CategoryModel.idCategory.in_(category_ids)).all()
    if len(categories) != len(category_ids):
        # Dette bør håndteres i routeren som en 400 Bad Request
        raise ValueError("Mindst én kategori ID er ugyldig.")
        
    db_budget.categories.extend(categories)
    
    try:
        db.add(db_budget)
        db.commit()
        db.refresh(db_budget)
        return db_budget
    except IntegrityError:
        db.rollback()
        # Dette bør håndteres i routeren
        raise ValueError("Integritetsfejl: Kontroller Account_idAccount eller andre Foreign Keys.")


def update_budget(db: Session, budget_id: int, budget: BudgetUpdate) -> Optional[BudgetModel]:
    """Opdaterer et eksisterende budget."""
    db_budget = get_budget_by_id(db, budget_id)
    if not db_budget:
        return None

    update_data = budget.model_dump(exclude_unset=True)
    
    # Håndter opdatering af mange-til-mange relationen (categories)
    if 'category_ids' in update_data:
        new_category_ids = update_data.pop('category_ids')
        categories = db.query(CategoryModel).filter(CategoryModel.idCategory.in_(new_category_ids)).all()
        # Erstat de eksisterende kategorier
        db_budget.categories = categories 

    # Opdater de øvrige felter
    for key, value in update_data.items():
        setattr(db_budget, key, value)
    
    try:
        db.commit()
        db.refresh(db_budget)
        return db_budget
    except IntegrityError:
        db.rollback()
        # Dette bør håndteres i routeren
        raise ValueError("Integritetsfejl ved opdatering.")


def delete_budget(db: Session, budget_id: int) -> bool:
    """Sletter et budget."""
    db_budget = get_budget_by_id(db, budget_id)
    if not db_budget:
        return False
        
    db.delete(db_budget)
    db.commit()
    return True


# --- Komplicerede logik/summary funktioner ---

def get_budget_summary(db: Session, account_id: int, month: int, year: int) -> BudgetSummary:
    """Beregner en detaljeret budgetopsummering for en specifik måned/år og konto."""
    
    # 1. Hent budgetter, der er knyttet til den pågældende konto og dækker perioden
    # Da din Budget-model nu har en many-to-many relation til Category,
    # antager jeg, at du vil summere budgetter baseret på `Account_idAccount`
    # og derefter slå op i `Transaction` for matchende `Category_idCategory`
    
    # Filtrerer efter den konto, det budget er tilknyttet
    budgets_query = db.query(BudgetModel).options(
        joinedload(BudgetModel.categories)
    ).filter(
        BudgetModel.Account_idAccount == account_id,
        # Filtrer BudgetModel efter budget_date (vi antager det er i den måned/år)
        extract('month', BudgetModel.budget_date) == month,
        extract('year', BudgetModel.budget_date) == year
    ).all()
    
    # 2. Hent de aggregerede udgifter for perioden
    expenses_by_category = _get_category_expenses_for_period(db, month, year)
    
    items: List[BudgetSummaryItem] = []
    total_budget = 0.0
    total_spent = 0.0
    over_budget_count = 0
    budget_category_ids = set()

    # 3. Gå gennem hvert budget og beregn status
    for budget in budgets_query:
        # Hvis et budget dækker flere kategorier, skal budgetbeløbet fordeles/håndteres her.
        # Baseret på din gamle kode, som havde en 1:1 relation, antager jeg,
        # at hvert BudgetModel i virkeligheden kun dækker én kategori for perioden.
        # Hvis det er 1:M, skal denne logik justeres.
        
        # Vi behandler det som 1:1, hvor Budget.categories[0] er den relevante kategori for simplicitet
        # BEMÆRK: Dette er en antagelse, da din modelstruktur har ændret sig til M:M.
        
        relevant_categories = budget.categories
        
        if not relevant_categories:
            continue # Spring budgetter uden kategorier over
            
        for category in relevant_categories:
            
            # Tjek for duplikat for at undgå at behandle samme kategori to gange (hvis flere budgetter peger på samme kategori)
            if category.idCategory in budget_category_ids:
                continue
            budget_category_ids.add(category.idCategory)
            
            spent = expenses_by_category.get(category.idCategory, 0.0)
            remaining = float(budget.amount) - spent
            percentage_used = (spent / float(budget.amount) * 100.0) if float(budget.amount) > 0 else 0.0
            
            if remaining < 0:
                over_budget_count += 1
                
            items.append(BudgetSummaryItem(
                category_id=category.idCategory,
                category_name=category.name,
                budget_amount=round(float(budget.amount), 2),
                spent_amount=round(spent, 2),
                remaining_amount=round(remaining, 2),
                percentage_used=round(percentage_used, 2)
            ))
            total_budget += float(budget.amount)
            total_spent += spent


    # 4. Inkluder kategorier med udgifter, men uden budget
    category_ids_with_expense = {cid for cid in expenses_by_category.keys() if cid is not None}
    missing_budget_category_ids = category_ids_with_expense - budget_category_ids
    
    if missing_budget_category_ids:
        categories = db.query(CategoryModel).filter(CategoryModel.idCategory.in_(missing_budget_category_ids)).all()
        id_to_name = {c.idCategory: c.name for c in categories}
        
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
            # Disse udgifter tælles ikke med i total_budget/total_spent i den gamle logik,
            # men i total_spent i det endelige resultat. Lad os opdatere total_spent
            total_spent += spent # Tæl udgifter uden budget med i totalen


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