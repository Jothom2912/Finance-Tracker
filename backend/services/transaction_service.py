# backend/services/transaction_service.py

from typing import List, Optional, Dict
from datetime import date
import pandas as pd
import io
import math

from backend.repository import get_transaction_repository, get_category_repository
from backend.shared.schemas.transaction import TransactionCreate
from backend.models.mysql.common import TransactionType
from .categorization import assign_category_automatically

def get_transaction_by_id(transaction_id: int) -> Optional[Dict]:
    """Henter en transaktion baseret på ID."""
    repo = get_transaction_repository()
    return repo.get_by_id(transaction_id)

def get_transactions(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    category_id: Optional[int] = None,
    tx_type: Optional[str] = None,
    month: Optional[str] = None,
    year: Optional[str] = None,
    account_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100
) -> List[Dict]:
    """Henter transaktioner med filtrering."""
    # KRITISK: account_id er påkrævet for at undgå at hente ALLE transaktioner
    if account_id is None:
        raise ValueError("Account ID er påkrævet for at hente transaktioner.")
    
    repo = get_transaction_repository()
    
    # Hent alle transaktioner med filtre
    transactions = repo.get_all(
        start_date=start_date,
        end_date=end_date,
        category_id=category_id,
        account_id=account_id,
        limit=limit,
        offset=skip
    )
    
    # Filtrer på type hvis angivet
    if tx_type:
        normalized_type = tx_type.strip().lower()
        transactions = [t for t in transactions if t.get("type", "").lower() == normalized_type]
    
    # Filtrer på måned/år hvis angivet
    if month is not None or year is not None:
        filtered = []
        for t in transactions:
            t_date = t.get("date")
            if t_date:
                if isinstance(t_date, str):
                    from datetime import datetime
                    try:
                        t_date = datetime.fromisoformat(t_date.replace('Z', '+00:00')).date()
                    except:
                        continue
                elif hasattr(t_date, 'date'):
                    t_date = t_date.date()
                
                if month is not None and t_date.month != int(month):
                    continue
                if year is not None and t_date.year != int(year):
                    continue
                filtered.append(t)
        transactions = filtered
    
    return transactions

def create_transaction(transaction: TransactionCreate) -> Dict:
    """Opretter en enkelt transaktion manuelt."""
    print(f"DEBUG create_transaction service: Modtaget transaction = {transaction.model_dump()}")
    print(f"DEBUG create_transaction service: transaction.Account_idAccount = {transaction.Account_idAccount}")
    print(f"DEBUG create_transaction service: transaction.Category_idCategory = {transaction.Category_idCategory}")

    # Validering af kategori
    category_repo = get_category_repository()
    category = category_repo.get_by_id(transaction.Category_idCategory)
    if not category:
        print(f"DEBUG create_transaction service: Kategori {transaction.Category_idCategory} findes ikke!")
        raise ValueError("Kategori med dette ID findes ikke.")
    print(f"DEBUG create_transaction service: Kategori fundet: {category.get('name')}")
    
    # Validering af account_id
    if not transaction.Account_idAccount:
        print(f"DEBUG create_transaction service: Account_idAccount er None eller 0 - fejler!")
        raise ValueError("Account ID er påkrævet for at oprette en transaktion.")
    print(f"DEBUG create_transaction service: Account_idAccount er OK: {transaction.Account_idAccount}")
    
    # Map schema fields to repository fields
    transaction_data = transaction.model_dump(by_alias=False)
    print(f"DEBUG create_transaction service: transaction_data (by_alias=False) = {transaction_data}")

    # Rename 'transaction_date' to 'date' for repository
    if 'transaction_date' in transaction_data:
        transaction_data['date'] = transaction_data.pop('transaction_date')
        print(f"DEBUG create_transaction service: Renamed transaction_date to date")

    # Convert type enum to string if needed
    if 'type' in transaction_data and hasattr(transaction_data['type'], 'value'):
        transaction_data['type'] = transaction_data['type'].value

    print(f"DEBUG create_transaction service: Final transaction_data = {transaction_data}")
    
    repo = get_transaction_repository()
    created = repo.create(transaction_data)
    print(f"DEBUG create_transaction service: Transaktion oprettet med ID: {created.get('idTransaction')}")
    return created

def update_transaction(transaction_id: int, transaction_data: TransactionCreate) -> Optional[Dict]:
    """Opdaterer en eksisterende transaktion."""
    repo = get_transaction_repository()
    existing = repo.get_by_id(transaction_id)
    if not existing:
        return None
        
    # Validering af kategori, hvis den opdateres
    if existing.get("Category_idCategory") != transaction_data.Category_idCategory:
        category_repo = get_category_repository()
        category = category_repo.get_by_id(transaction_data.Category_idCategory)
        if not category:
            raise ValueError("Kategori med dette ID findes ikke.")

    update_data = transaction_data.model_dump(exclude_unset=True, by_alias=False)
    # Rename 'transaction_date' to 'date' for repository
    if 'transaction_date' in update_data:
        update_data['date'] = update_data.pop('transaction_date')
    
    # Convert type enum to string if needed
    if 'type' in update_data and hasattr(update_data['type'], 'value'):
        update_data['type'] = update_data['type'].value
    
    return repo.update(transaction_id, update_data)

def delete_transaction(transaction_id: int) -> bool:
    """Sletter en transaktion."""
    repo = get_transaction_repository()
    return repo.delete(transaction_id)

# --- CSV Import Logik ---

def import_transactions_from_csv(file_contents: bytes, account_id: int) -> List[Dict]:
    """
    Udfører parsing og import af transaktioner fra en CSV-fil.
    """
    csv_file = io.StringIO(file_contents.decode('utf-8'))

    # Første: Læs og rens data
    df = pd.read_csv(
        csv_file,
        sep=';',
        decimal=',',
        thousands='.',
        dtype={'Beløb': str}
    )

    df['date'] = pd.to_datetime(df['Bogføringsdato'], errors='coerce', format='%Y/%m/%d')
    df.dropna(subset=['date'], inplace=True)
    df['amount'] = df['Beløb'].str.replace('.', '', regex=False).str.replace(',', '.', regex=False).astype(float)
    
    # Hent kategorier
    category_repo = get_category_repository()
    categories = category_repo.get_all()
    category_name_to_id = {cat.get("name", "").lower(): cat.get("idCategory") for cat in categories if cat.get("name")}

    # Opret "Anden" kategori hvis den mangler
    if "anden" not in category_name_to_id:
        try:
            default_category = category_repo.create({
                "name": "Anden",
                "type": TransactionType.expense.value
            })
            category_name_to_id["anden"] = default_category.get("idCategory")
        except Exception as e:
            raise ValueError(f"Kunne ikke oprette standardkategorien 'Anden': {str(e)}")
        
    created_transactions: List[Dict] = []
    transaction_repo = get_transaction_repository()

    try:
        # Anden: Iterer over rækker, kategoriser og gem
        for _, row in df.iterrows():
            full_description = f"{row.get('Modtager', '')} {row.get('Afsender', '')} {row.get('Navn', '')} {row.get('Beskrivelse', '')}".strip()
            full_description = " ".join(full_description.split())
            if not full_description:
                full_description = "Ukendt beskrivelse"

            transaction_category_id = assign_category_automatically(
                transaction_description=full_description,
                amount=row['amount'],
                category_name_to_id=category_name_to_id
            )
            
            # Håndter NaN / None for kolonner, der ikke er nødvendige
            def clean_value(val):
                return None if (isinstance(val, float) and math.isnan(val)) else val

            tx_type = TransactionType.income.value if row['amount'] >= 0 else TransactionType.expense.value
            
            transaction_data = {
                "date": row['date'].date().isoformat() if hasattr(row['date'], 'date') else str(row['date']),
                "amount": float(row['amount']),
                "description": full_description,
                "type": tx_type,
                "Category_idCategory": transaction_category_id,
                "Account_idAccount": account_id
            }

            created = transaction_repo.create(transaction_data)
            created_transactions.append(created)
            
        print(f"✓ Succesfuldt importeret {len(created_transactions)} transaktioner til account_id={account_id}")
        return created_transactions
    except Exception as e:
        print(f"✗ Fejl ved import: {str(e)}")
        raise ValueError(f"Fejl ved import af transaktioner: {str(e)}")
