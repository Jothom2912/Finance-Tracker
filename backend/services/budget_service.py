from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, extract
from sqlalchemy.exc import IntegrityError
from typing import List, Optional, Dict, Any

from backend.models.mysql.budget import Budget as BudgetModel # Antag at du bruger alias for at undgå navnekollision
from backend.models.mysql.category import Category as CategoryModel
from backend.models.mysql.transaction import Transaction as TransactionModel
from backend.shared.schemas.budget import BudgetCreate, BudgetUpdate, BudgetSummary, BudgetSummaryItem

# --- Hjælpefunktioner ---

def _get_category_expenses_for_period(db: Session, month: int, year: int, account_id: int) -> Dict[int, float]:
    """Henter aggregerede udgifter for hver kategori for en given måned og år."""
    
    # Filtrer for at sikre, at vi kun tager udgifter (amount < 0) og kun fra den specifikke account
    # Aggreger efter Category_idCategory
    expenses_by_category = db.query(
        TransactionModel.Category_idCategory.label('category_id'),
        func.sum(TransactionModel.amount).label('total_spent')
    ).filter(
        TransactionModel.Account_idAccount == account_id,  # KRITISK: Filtrer på account_id
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
    
    # Validering af account_id
    if not budget.Account_idAccount:
        raise ValueError("Account ID er påkrævet for at oprette et budget.")
    
    budget_data = budget.model_dump(exclude={'month', 'year', 'category_id'})
    
    # Hent category_id hvis det er angivet (fra frontend)
    category_id = None
    if hasattr(budget, 'category_id') and budget.category_id:
        category_id = budget.category_id
    
    db_budget = BudgetModel(**budget_data)
    
    try:
        db.add(db_budget)
        db.flush()  # Få ID før vi tilføjer categories
        
        # Tilføj kategori til budget via association table hvis category_id er angivet
        if category_id:
            from backend.models.mysql.common import budget_category_association
            
            # Valider at kategorien eksisterer
            category = db.query(CategoryModel).filter(CategoryModel.idCategory == category_id).first()
            if not category:
                db.rollback()
                raise ValueError(f"Kategori med ID {category_id} findes ikke.")
            
            # Tilføj via association table
            db.execute(
                budget_category_association.insert().values(
                    Budget_idBudget=db_budget.idBudget,
                    Category_idCategory=category_id
                )
            )
        
        db.commit()
        db.refresh(db_budget)
        return db_budget
    except IntegrityError:
        db.rollback()
        raise ValueError("Integritetsfejl: Kontroller Account_idAccount eller andre Foreign Keys.")


def update_budget(db: Session, budget_id: int, budget: BudgetUpdate) -> Optional[BudgetModel]:
    """Opdaterer et eksisterende budget."""
    db_budget = get_budget_by_id(db, budget_id)
    if not db_budget:
        return None

    update_data = budget.model_dump(exclude_unset=True)
    
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
    
    # Håndter category_id - opdater association table
    category_id = update_data.pop('category_id', None)
    if category_id is not None:
        from backend.models.mysql.common import budget_category_association
        
        # Valider at kategorien eksisterer
        category = db.query(CategoryModel).filter(CategoryModel.idCategory == category_id).first()
        if not category:
            raise ValueError(f"Kategori med ID {category_id} findes ikke.")
        
        # Fjern eksisterende kategorier
        db.execute(
            budget_category_association.delete().where(
                budget_category_association.c.Budget_idBudget == budget_id
            )
        )
        
        # Tilføj ny kategori
        db.execute(
            budget_category_association.insert().values(
                Budget_idBudget=budget_id,
                Category_idCategory=category_id
            )
        )

    # Opdater felterne
    for key, value in update_data.items():
        setattr(db_budget, key, value)
    
    try:
        db.commit()
        db.refresh(db_budget)
        return db_budget
    except IntegrityError:
        db.rollback()
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
    # Håndter både budgetter med og uden budget_date
    budgets_query = db.query(BudgetModel).options(
        joinedload(BudgetModel.categories)
    ).filter(
        BudgetModel.Account_idAccount == account_id
    ).all()
    
    # Filtrer manuelt efter month/year hvis budget_date er sat
    # Hvis budget_date er None, inkluder budgettet (for bagudkompatibilitet)
    filtered_budgets = []
    for budget in budgets_query:
        if budget.budget_date:
            budget_month = budget.budget_date.month
            budget_year = budget.budget_date.year
            if budget_month == month and budget_year == year:
                filtered_budgets.append(budget)
        # Hvis budget_date er None, inkluder det ikke (kræver budget_date for at matche periode)
    
    budgets_query = filtered_budgets
    
    # 2. Hent de aggregerede udgifter for perioden (kun for denne account)
    expenses_by_category = _get_category_expenses_for_period(db, month, year, account_id)
    
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