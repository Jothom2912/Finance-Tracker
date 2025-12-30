# backend/services/transaction_service.py

from backend.repository import get_transaction_repository
from typing import List, Optional, Dict
from datetime import date
import pandas as pd
import io
import math

# --- KORREKTE IMPORTS TIL NY MODELSTRUKTUR ---
from backend.models.mysql.transaction import Transaction as TransactionModel
from backend.models.mysql.category import Category as CategoryModel
from backend.models.mysql.common import TransactionType  # <--- RETTET STED: HENTES FRA COMMON
from backend.shared.schemas.transaction import TransactionCreate

from .categorization import assign_category_automatically

# --- (RESTEN AF DIN KODE FOR TRANSACTION SERVICE) ---

def get_transaction_by_id(transaction_id: int) -> Optional[TransactionModel]:
    """Get transaction by ID using active database"""
    repo = get_transaction_repository()
    return repo.get_by_id(transaction_id)

def get_transactions(account_id: int, skip: int = 0, limit: int = 100) -> List[Dict]:
    """Get transactions using active database"""
    repo = get_transaction_repository()
    return repo.get_all(
        account_id=account_id,
        limit=limit,
        offset=skip
    )

def create_transaction(transaction_data: Dict) -> Dict:
    """Create transaction using active database"""
    repo = get_transaction_repository()
    return repo.create(transaction_data)

def update_transaction( transaction_id: int, transaction_data: TransactionCreate) -> Optional[TransactionModel]:
    """Create transaction using active database"""
    repo = get_transaction_repository()
    return repo.update(transaction_data, transaction_id)

def delete_transaction( transaction_id: int) -> bool:
    """Sletter en transaktion."""
    repo = get_transaction_repository()
    db_transaction = get_transaction_by_id(transaction_id)
    if not db_transaction:
        return False
    repo.delete(transaction_id)
    return True

# --- CSV Import Logik ---

def import_transactions_from_csv(db: Session, file_contents: bytes, account_id: int) -> List[TransactionModel]:
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
    categories = db.query(CategoryModel).all()
    category_name_to_id = {cat.name.lower(): cat.idCategory for cat in categories}

    # Opret "Anden" kategori hvis den mangler
    if "anden" not in category_name_to_id:
        try:
            default_category = CategoryModel(
                name="Anden",
                type=TransactionType.expense.value
            )
            db.add(default_category)
            db.commit()
            db.refresh(default_category)
            category_name_to_id["anden"] = default_category.idCategory
        except Exception as e:
            db.rollback()
            raise ValueError(f"Kunne ikke oprette standardkategorien 'Anden': {str(e)}")
        
    created_transactions: List[TransactionModel] = []

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
            
            db_transaction = TransactionModel(
                date=row['date'].date(),
                amount=row['amount'],
                description=full_description,
                type=tx_type,
                Category_idCategory=transaction_category_id,
                Account_idAccount=account_id
                # Mapp ikke-nødvendige kolonner fra CSV:
                # balance_after=clean_value(row.get('Saldo')),
                # currency=row.get('Valuta', 'DKK'),
                # sender=clean_value(row.get('Afsender')),
                # recipient=clean_value(row.get('Modtager')),
                # name=clean_value(row.get('Navn'))
            )

            db.add(db_transaction)
            db.flush() 
            created_transactions.append(db_transaction)
            
        db.commit()
        print(f"✓ Succesfuldt importeret {len(created_transactions)} transaktioner til account_id={account_id}")
        return created_transactions
    except Exception as e:
        db.rollback()
        print(f"✗ Fejl ved import: {str(e)}")
        raise ValueError(f"Fejl ved import af transaktioner: {str(e)}")