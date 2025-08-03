# backend/re_categorize_transactions.py

from sqlalchemy.orm import Session
from backend.database import SessionLocal, Category, Transaction # Importér dine modeller og SessionLocal
from backend.service.categorization import assign_category_automatically
import sys

def re_categorize_all_transactions():
    """
    Henter alle transaktioner fra databasen og genanvender kategoriseringslogikken.
    Opdaterer kun transaktioner, hvor den nye kategori er forskellig fra den eksisterende.
    """
    db: Session = SessionLocal() # Opret en ny database session
    try:
        # 1. Hent alle kategorier for at bygge category_name_to_id ordbogen
        categories = db.query(Category).all()
        category_name_to_id = {cat.name.lower(): cat.id for cat in categories}

        # Tjek om "anden" kategori findes, da den er vores fallback
        if "anden" not in category_name_to_id:
            print("FEJL: Standardkategorien 'Anden' blev ikke fundet i databasen.")
            print("Sørg for at køre 'python -m backend.seed_categories' først for at oprette den.")
            sys.exit(1) # Afslut scriptet, hvis "Anden" mangler

        # 2. Hent alle transaktioner, der skal (gen)kategoriseres
        # Du kan vælge at filtrere her, f.eks. kun transaktioner uden kategori:
        # transactions_to_reprocess = db.query(Transaction).filter(Transaction.category_id.is_(None)).all()
        # Eller for at genbehandle ALLE transaktioner:
        transactions_to_reprocess = db.query(Transaction).all()

        print(f"Starter genkategorisering af {len(transactions_to_reprocess)} transaktioner...")

        updated_count = 0
        for trans in transactions_to_reprocess:
            # Sørg for at description ikke er None, før den sendes til kategoriseringsfunktionen
            full_description = trans.description if trans.description else ""

            # Kalder den automatiske kategoriseringsfunktion
            new_category_id = assign_category_automatically(
                transaction_description=full_description,
                amount=trans.amount,
                category_name_to_id=category_name_to_id
            )

            # Opdater kun transaktionen, hvis den nye kategori er forskellig fra den nuværende
            if trans.category_id != new_category_id:
                trans.category_id = new_category_id
                db.add(trans) # Tilføj transaktionen til sessionen for at den bliver opdateret
                updated_count += 1

        db.commit() # Gem alle ændringer i én transaktion
        print(f"Genkategorisering færdig. {updated_count} transaktioner blev opdateret.")

    except Exception as e:
        db.rollback() # Rul tilbage alle ændringer, hvis der opstår en fejl
        print(f"Der opstod en fejl under genkategorisering: {e}")
    finally:
        db.close() # Luk database sessionen

if __name__ == "__main__":
    re_categorize_all_transactions()