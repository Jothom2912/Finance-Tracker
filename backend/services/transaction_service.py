# backend/services/transaction_service.py

from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict
from datetime import date
import pandas as pd
import io
import math

# --- KORREKTE IMPORTS TIL NY MODELSTRUKTUR ---
from ..models.transaction import Transaction as TransactionModel
from ..models.category import Category as CategoryModel
from ..models.common import TransactionType  # <--- RETTET STED: HENTES FRA COMMON
from ..schemas.transaction import TransactionCreate

from .categorization import assign_category_automatically

# --- (RESTEN AF DIN KODE FOR TRANSACTION SERVICE) ---

def get_transaction_by_id(db: Session, transaction_id: int) -> Optional[TransactionModel]:
    """Henter en transaktion baseret på ID."""
    return db.query(TransactionModel).filter(TransactionModel.idTransaction == transaction_id).first()

def get_transactions(
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    category_id: Optional[int] = None,
    tx_type: Optional[str] = None,
    month: Optional[str] = None,
    year: Optional[str] = None,
    account_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100
) -> List[TransactionModel]:
    """Henter transaktioner med filtrering."""
    query = db.query(TransactionModel)
    
    # Filtrer på account_id hvis angivet
    if account_id is not None:
        query = query.filter(TransactionModel.Account_idAccount == account_id)
    
    if start_date:
        query = query.filter(TransactionModel.date >= start_date)
    if end_date:
        query = query.filter(TransactionModel.date <= end_date)
    if category_id is not None:
        query = query.filter(TransactionModel.Category_idCategory == category_id)

    if tx_type:
        normalized_type = tx_type.strip().lower()
        if normalized_type == "income":
            query = query.filter(TransactionModel.type == TransactionType.income.value)
        elif normalized_type == "expense":
            query = query.filter(TransactionModel.type == TransactionType.expense.value)

    if month is not None:
        query = query.filter(func.strftime('%m', TransactionModel.date) == month)
    if year is not None:
        query = query.filter(func.strftime('%Y', TransactionModel.date) == year)

    return query.offset(skip).limit(limit).all()

def create_transaction(db: Session, transaction: TransactionCreate) -> TransactionModel:
    """Opretter en enkelt transaktion manuelt."""
    # Validering af kategori
    category = db.query(CategoryModel).filter(CategoryModel.idCategory == transaction.Category_idCategory).first()
    if not category:
        raise ValueError("Kategori med dette ID findes ikke.")
        
    db_transaction = TransactionModel(**transaction.model_dump())
    
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)
    return db_transaction

def update_transaction(db: Session, transaction_id: int, transaction_data: TransactionCreate) -> Optional[TransactionModel]:
    """Opdaterer en eksisterende transaktion."""
    db_transaction = get_transaction_by_id(db, transaction_id)
    if not db_transaction:
        return None
        
    # Validering af kategori, hvis den opdateres
    if db_transaction.Category_idCategory != transaction_data.Category_idCategory:
        category = db.query(CategoryModel).filter(CategoryModel.idCategory == transaction_data.Category_idCategory).first()
        if not category:
            raise ValueError("Kategori med dette ID findes ikke.")

    update_data = transaction_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_transaction, key, value)
    
    db.commit()
    db.refresh(db_transaction)
    return db_transaction

def delete_transaction(db: Session, transaction_id: int) -> bool:
    """Sletter en transaktion."""
    db_transaction = get_transaction_by_id(db, transaction_id)
    if not db_transaction:
        return False
        
    db.delete(db_transaction)
    db.commit()
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