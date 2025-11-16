from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import date
import pandas as pd
import io
import math

# --- VIGTIGE ÆNDRINGER HER ---
# Brug relative imports for moduler inden for pakken
from ..schemas.category import Category as CategorySchema
from ..schemas.transaction import Transaction as TransactionSchema, TransactionCreate # <-- Tilføjet/Rettet
# Importér dine SQLAlchemy-modeller direkte fra database.py
from ..database import get_db, Category, Transaction # <-- Rettet til relativ import
from ..service.categorization import assign_category_automatically # <-- Rettet til relativ import

router = APIRouter(
    prefix="/transactions",
    tags=["Transactions"],
)

# --- Endpoint til at oprette en enkelt transaktion manuelt ---
@router.post("/", response_model=TransactionSchema) # <-- Rettet
def create_transaction(transaction: TransactionCreate, db: Session = Depends(get_db)): # <-- Rettet
    """
    Opretter en ny transaktion manuelt.
    """
    # Brug den importerede Category-model direkte
    category = db.query(Category).filter(Category.id == transaction.category_id).first()
    if not category:
        raise HTTPException(status_code=400, detail="Kategori med dette ID findes ikke.")

    # Brug den importerede Transaction-model direkte
    db_transaction = Transaction(**transaction.model_dump())
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)
    return db_transaction

### Importér transaktioner fra CSV
@router.post("/upload-csv/", response_model=List[TransactionSchema]) # <-- Rettet
async def upload_transactions_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Uploader en CSV-fil med banktransaktioner, parser dem og gemmer dem i databasen.
    Automatisk kategoriserer transaktionerne baseret på foruddefinerede regler.
    Returnerer en liste over de succesfuldt oprettede transaktioner.
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ugyldig filtype. Kun CSV-filer er tilladt."
        )

    try:
        contents = await file.read()
        csv_file = io.StringIO(contents.decode('utf-8'))

        df = pd.read_csv(
            csv_file,
            sep=';',
            decimal=',',
            thousands='.',
            dtype={'Beløb': str}
        )

        df['Bogføringsdato'] = pd.to_datetime(df['Bogføringsdato'], errors='coerce', format='%Y/%m/%d')
        df.dropna(subset=['Bogføringsdato'], inplace=True)

        df['Beløb'] = df['Beløb'].str.replace('.', '', regex=False).str.replace(',', '.', regex=False).astype(float)

        # Brug den importerede Category-model direkte
        categories = db.query(Category).all()
        category_name_to_id = {cat.name.lower(): cat.id for cat in categories}

        if "anden" not in category_name_to_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Standardkategorien 'Anden' blev ikke fundet i databasen. Opret den venligst."
            )

        created_transactions: List[TransactionSchema] = [] # <-- Rettet
        for index, row in df.iterrows():
            full_description = f"{row.get('Modtager', '')} {row.get('Afsender', '')} {row.get('Navn', '')} {row.get('Beskrivelse', '')}".strip()
            full_description = " ".join(full_description.split())
            if not full_description:
                full_description = "Ukendt beskrivelse"

            transaction_category_id = assign_category_automatically(
                transaction_description=full_description,
                amount=row['Beløb'],
                category_name_to_id=category_name_to_id
            )

            # Konverter nan til None (MySQL tillader ikke nan)
            import math
            sender = row.get('Afsender')
            recipient = row.get('Modtager')
            name = row.get('Navn')
            balance_after = row.get('Saldo')
            
            # Tjek for nan og konverter til None
            sender = None if (isinstance(sender, float) and math.isnan(sender)) else sender
            recipient = None if (isinstance(recipient, float) and math.isnan(recipient)) else recipient
            name = None if (isinstance(name, float) and math.isnan(name)) else name
            balance_after = None if (isinstance(balance_after, float) and math.isnan(balance_after)) else balance_after

            # Brug den importerede Transaction-model direkte
            db_transaction = Transaction(
                date=row['Bogføringsdato'].date(),
                amount=row['Beløb'],
                description=full_description,
                category_id=transaction_category_id,
                balance_after=balance_after,
                currency=row.get('Valuta', 'DKK'),
                sender=sender,
                recipient=recipient,
                name=name
            )

            db.add(db_transaction)
            db.flush()
            db.refresh(db_transaction)
            created_transactions.append(TransactionSchema.model_validate(db_transaction)) # <-- Rettet

        db.commit()
        return created_transactions

    except pd.errors.EmptyDataError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Den uploadede CSV-fil er tom."
        )
    except pd.errors.ParserError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kunne ikke parse CSV-filen. Kontrollér venligst formatet (semikolon-separeret, komma som decimal)."
        )
    except KeyError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Mangler en forventet kolonne i CSV-filen: {e}. Tjek venligst, at alle påkrævede kolonner ('Bogføringsdato', 'Beløb', 'Modtager', 'Afsender', 'Navn', 'Beskrivelse') er til stede og korrekt navngivet."
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Der opstod en uventet fejl under CSV-importen: {str(e)}"
        )

### Hent transaktioner med filtrering
@router.get("/", response_model=List[TransactionSchema]) # <-- Rettet
def read_transactions(
    start_date: Optional[date] = Query(None, description="Startdato for filtrering (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="Slutdato for filtrering (YYYY-MM-DD)"),
    category_id: Optional[int] = Query(None, description="Filtrer efter kategori ID"),
    type: Optional[str] = Query(None, description="Filtrer efter type: 'income' eller 'expense'"),
    month: Optional[str] = Query(None, description="Måned i MM format (f.eks. '01')"),
    year: Optional[str] = Query(None, description="År i YYYY format (f.eks. '2024')"),
    skip: int = Query(0, description="Antal transaktioner der skal springes over (paginering)"),
    limit: int = Query(100, description="Maksimalt antal transaktioner der skal returneres (paginering)"),
    db: Session = Depends(get_db)
):
    """
    Henter en liste over transaktioner, med mulighed for paginering, dato- og kategori-filtrering.
    """
    # Brug den importerede Transaction-model direkte
    query = db.query(Transaction)

    if start_date:
        query = query.filter(Transaction.date >= start_date)
    if end_date:
        query = query.filter(Transaction.date <= end_date)

    if category_id is not None:
        query = query.filter(Transaction.category_id == category_id)

    # Filter by transaction type if provided
    if type is not None:
        normalized_type = type.strip().lower()
        if normalized_type not in {"income", "expense"}:
            raise HTTPException(status_code=400, detail="Ugyldig type. Brug 'income' eller 'expense'.")
        from ..database import TransactionType as TxType
        query = query.filter(Transaction.type == (TxType.income if normalized_type == "income" else TxType.expense))

    # Filter by month and year if provided (based on Transaction.date)
    # Use SQLite-compatible strftime via SQLAlchemy func for portability in this project
    if month is not None:
        if len(month) != 2:
            raise HTTPException(status_code=400, detail="Ugyldig måned. Brug MM format, f.eks. '01'.")
        query = query.filter(func.strftime('%m', Transaction.date) == month)
    if year is not None:
        if len(year) != 4:
            raise HTTPException(status_code=400, detail="Ugyldigt år. Brug YYYY format, f.eks. '2024'.")
        query = query.filter(func.strftime('%Y', Transaction.date) == year)

    transactions = query.offset(skip).limit(limit).all()
    return transactions

### Hent en specifik transaktion
@router.get("/{transaction_id}", response_model=TransactionSchema) # <-- Rettet
def read_transaction(transaction_id: int, db: Session = Depends(get_db)):
    """
    Henter detaljer for en specifik transaktion baseret på ID.
    """
    # Brug den importerede Transaction-model direkte
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaktion ikke fundet.")
    return transaction

### Opdater en transaktion
@router.put("/{transaction_id}", response_model=TransactionSchema) # <-- Rettet
def update_transaction(transaction_id: int, transaction: TransactionCreate, db: Session = Depends(get_db)): # <-- Rettet
    """
    Opdaterer en eksisterende transaktion baseret på ID.
    """
    # Brug den importerede Transaction-model direkte
    db_transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if db_transaction is None:
        raise HTTPException(status_code=404, detail="Transaktion ikke fundet.")

    # Brug den importerede Category-model direkte
    category = db.query(Category).filter(Category.id == transaction.category_id).first()
    if not category:
        raise HTTPException(status_code=400, detail="Kategori med dette ID findes ikke.")

    # Opdater transaktionens felter
    for key, value in transaction.model_dump(exclude_unset=True).items():
        setattr(db_transaction, key, value)

    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)
    return db_transaction # <-- Rettet (var db_transactions)