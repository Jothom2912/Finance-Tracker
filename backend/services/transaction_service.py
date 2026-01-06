# backend/services/transaction_service.py

from typing import List, Optional, Dict
from datetime import date, datetime
from sqlalchemy.orm import Session
import pandas as pd
import io
import math

from backend.repositories import get_transaction_repository, get_category_repository
from backend.shared.schemas.transaction import TransactionCreate
from backend.models.mysql.common import TransactionType
from .categorization import assign_category_automatically

def get_transaction_by_id(transaction_id: int, db: Session) -> Optional[Dict]:
    """Henter en transaktion baseret på ID."""
    repo = get_transaction_repository(db)
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
    limit: int = 100,
    db: Session = None
) -> List[Dict]:
    """Henter transaktioner med filtrering."""
    # KRITISK: account_id er påkrævet for at undgå at hente ALLE transaktioner
    if account_id is None:
        raise ValueError("Account ID er påkrævet for at hente transaktioner.")
    
    if db is None:
        raise ValueError("db: Session parameter is required")
    
    repo = get_transaction_repository(db)
    
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
                # ✅ Brug global datetime import - ingen lokal import
                if isinstance(t_date, str):
                    try:
                        t_date = datetime.fromisoformat(t_date.replace('Z', '+00:00')).date()
                    except:
                        continue
                elif hasattr(t_date, 'date'):
                    t_date = t_date.date()
                elif not isinstance(t_date, date):
                    continue
                
                if month is not None and t_date.month != int(month):
                    continue
                if year is not None and t_date.year != int(year):
                    continue
                filtered.append(t)
        transactions = filtered
    
    return transactions

def create_transaction(transaction: TransactionCreate, db: Session) -> Dict:
    """Opretter en enkelt transaktion manuelt."""
    print(f"DEBUG create_transaction service: Modtaget transaction = {transaction.model_dump()}")
    print(f"DEBUG create_transaction service: transaction.Account_idAccount = {transaction.Account_idAccount}")
    print(f"DEBUG create_transaction service: transaction.Category_idCategory = {transaction.Category_idCategory}")

    # Validering af kategori
    category_repo = get_category_repository(db)
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

    # Ensure 'date' is set - if None or not provided, default to today's date
    if 'date' not in transaction_data or transaction_data.get('date') is None:
        transaction_data['date'] = date.today()
        print(f"DEBUG create_transaction service: date was None or missing, set to today: {transaction_data['date']}")
    else:
        print(f"DEBUG create_transaction service: date is set: {transaction_data['date']}")

    # Convert type enum to string if needed
    if 'type' in transaction_data and hasattr(transaction_data['type'], 'value'):
        transaction_data['type'] = transaction_data['type'].value

    # Set created_at timestamp if not already set
    if 'created_at' not in transaction_data:
        transaction_data['created_at'] = datetime.now()

    print(f"DEBUG create_transaction service: Final transaction_data = {transaction_data}")
    
    repo = get_transaction_repository(db)
    created = repo.create(transaction_data)
    print(f"DEBUG create_transaction service: Transaktion oprettet med ID: {created.get('idTransaction')}")
    return created

def update_transaction(transaction_id: int, transaction_data: TransactionCreate, db: Session) -> Optional[Dict]:
    """Opdaterer en eksisterende transaktion."""
    repo = get_transaction_repository(db)
    existing = repo.get_by_id(transaction_id)
    if not existing:
        return None
        
    # Validering af kategori, hvis den opdateres
    if existing.get("Category_idCategory") != transaction_data.Category_idCategory:
        category_repo = get_category_repository(db)
        category = category_repo.get_by_id(transaction_data.Category_idCategory)
        if not category:
            raise ValueError("Kategori med dette ID findes ikke.")

    update_data = transaction_data.model_dump(exclude_unset=True, by_alias=False)
    # If 'date' is None in update_data, remove it (keep existing date)
    if 'date' in update_data and update_data['date'] is None:
        update_data.pop('date')
    
    # Convert type enum to string if needed
    if 'type' in update_data and hasattr(update_data['type'], 'value'):
        update_data['type'] = update_data['type'].value
    
    return repo.update(transaction_id, update_data)

def delete_transaction(transaction_id: int, db: Session) -> bool:
    """Sletter en transaktion."""
    repo = get_transaction_repository(db)
    return repo.delete(transaction_id)

# --- CSV Import Logik ---

def import_transactions_from_csv(file_contents: bytes, account_id: int, db: Session) -> List[Dict]:
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

    # ✅ Parse date kolonne - prøv forskellige formater
    if 'Bogføringsdato' in df.columns:
        # Prøv dansk format først (dd-mm-yyyy eller dd/mm/yyyy)
        df['date'] = pd.to_datetime(df['Bogføringsdato'], errors='coerce', format='%d-%m-%Y')
        # Hvis det fejler, prøv med slash
        if df['date'].isna().all():
            df['date'] = pd.to_datetime(df['Bogføringsdato'], errors='coerce', format='%d/%m/%Y')
        # Hvis det stadig fejler, prøv ISO format
        if df['date'].isna().all():
            df['date'] = pd.to_datetime(df['Bogføringsdato'], errors='coerce', format='%Y/%m/%d')
        # Hvis det stadig fejler, prøv auto-detect
        if df['date'].isna().all():
            df['date'] = pd.to_datetime(df['Bogføringsdato'], errors='coerce')
    elif 'Dato' in df.columns:
        df['date'] = pd.to_datetime(df['Dato'], errors='coerce', format='%d-%m-%Y')
        if df['date'].isna().all():
            df['date'] = pd.to_datetime(df['Dato'], errors='coerce')
    elif 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
    else:
        raise ValueError("CSV mangler 'Bogføringsdato', 'Dato' eller 'date' kolonne")
    
    # Fjern rækker uden valid date
    df = df.dropna(subset=['date'])
    
    if df.empty:
        raise ValueError("Ingen gyldige transaktioner fundet i CSV efter date parsing")
    
    # Konverter til date objekter (ikke datetime)
    df['date'] = df['date'].dt.date
    
    # Parse amount
    df['amount'] = df['Beløb'].str.replace('.', '', regex=False).str.replace(',', '.', regex=False).astype(float)
    
    # Hent kategorier
    category_repo = get_category_repository(db)
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
    transaction_repo = get_transaction_repository(db)

    try:
        # Iterer over rækker, kategoriser og gem
        for idx, row in df.iterrows():
            try:
                # Parse amount
                amount = float(row['amount'])
                
                # Build description - fjern 'nan' værdier
                parts = [
                    str(row.get('Modtager', '')),
                    str(row.get('Afsender', '')),
                    str(row.get('Navn', '')),
                    str(row.get('Beskrivelse', ''))
                ]
                # Fjern 'nan', 'NaN', tomme strings og whitespace
                cleaned_parts = [p for p in parts if p and p.lower() != 'nan' and p.strip()]
                full_description = " ".join(cleaned_parts).strip()
                if not full_description:
                    full_description = "Ukendt beskrivelse"

                # Auto-assign category
                transaction_category_id = assign_category_automatically(
                    transaction_description=full_description,
                    amount=amount,
                    category_name_to_id=category_name_to_id
                )
                
                # Determine transaction type
                tx_type = TransactionType.income.value if amount >= 0 else TransactionType.expense.value
                
                # ✅ Date er allerede parsed til date objekt i DataFrame
                # Ingen behov for yderligere konvertering - brug direkte
                transaction_date = row['date']
                
                # ✅ Opret transaction data - INGEN local 'datetime' variable
                transaction_data = {
                    "date": transaction_date,  # ✅ Allerede et date objekt
                    "amount": abs(amount),  # Gem som positiv værdi
                    "description": full_description,
                    "type": tx_type,
                    "Category_idCategory": transaction_category_id,
                    "Account_idAccount": account_id,
                    "created_at": datetime.now()  # ✅ Bruger global datetime import
                }

                created = transaction_repo.create(transaction_data)
                created_transactions.append(created)
                
            except Exception as row_error:
                print(f"⚠️ Fejl ved import af række {idx}: {row_error}")
                continue  # Skip denne række og fortsæt med næste
        
        if not created_transactions:
            raise ValueError("Ingen transaktioner kunne importeres fra CSV")
        
        print(f"✓ Succesfuldt importeret {len(created_transactions)} transaktioner til account_id={account_id}")
        return created_transactions
        
    except pd.errors.EmptyDataError:
        raise ValueError("CSV filen er tom")
    except KeyError as e:
        raise ValueError(f"Fejl i CSV format - manglende kolonne: {e}")
    except Exception as e:
        print(f"✗ Fejl ved import: {str(e)}")
        raise ValueError(f"Fejl ved import af transaktioner: {str(e)}")
