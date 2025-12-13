# seed_categories.py
import os
import sys
from sqlalchemy.orm import Session # For type hint

# I Docker containeren:
# - Volume mount: ./backend:/app betyder at alt fra backend/ mappen er i /app/
# - Strukturen bliver: /app/database/, /app/models/, /app/seed_categories.py
# - Men imports bruger "from backend.xxx", så Python skal kunne finde "backend" modulet
#
# Løsning: Tilføj /app til sys.path så Python kan finde backend modulet
# Når vi er i /app/ og importerer "from backend.xxx", leder Python efter /app/backend/xxx
# Men strukturen er /app/xxx, så vi skal oprette en symlink eller ændre path
#
# Faktisk: uvicorn kører "backend.main:app" hvilket virker, så Python må kunne finde det.
# Det betyder at enten PYTHONPATH er sat, eller strukturen er faktisk /app/backend/
#
# Lad os tilføje /app til sys.path og håbe det virker
script_dir = os.path.dirname(os.path.abspath(__file__))
# script_dir er /app i containeren
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

# Importér moduler med den fulde pakke-sti
from backend.database.mysql import SessionLocal, engine, Base, create_db_tables
from backend.models.mysql.category import Category
from backend.services.categorization import category_rules
from backend.models.mysql.common import TransactionType


# Sørg for at databasetabellerne er oprettet
create_db_tables()

def seed_categories():
    db: Session = SessionLocal()
    try:
        existing_categories = {cat.name.lower() for cat in db.query(Category).all()}

        categories_to_add = []
        for category_name in set(category_rules.values()):
            if category_name.lower() not in existing_categories:
                # Bestem type baseret på kategorinavn
                category_type = TransactionType.expense.value
                if any(keyword in category_name.lower() for keyword in ["indkomst", "løn", "støtte", "renter", "opsparing (ind)", "mobilepay ind", "betalinger fra andre"]):
                    category_type = TransactionType.income.value
                elif "mobilepay ud" in category_name.lower():
                    category_type = TransactionType.expense.value

                categories_to_add.append(Category(name=category_name, type=category_type))

        # Sørg for at "Anden" kategori findes (fallback kategori) - tjek igen efter at have tilføjet andre
        if "anden" not in existing_categories and "anden" not in {cat.lower() for cat in set(category_rules.values())}:
            categories_to_add.append(Category(name="Anden", type=TransactionType.expense.value))

        if categories_to_add:
            db.add_all(categories_to_add)
            db.commit()
            print(f"Tilføjet {len(categories_to_add)} nye kategorier til databasen.")
        else:
            print("Alle kategorier fra category_rules eksisterer allerede i databasen.")

    except Exception as e:
        db.rollback()
        print(f"Fejl ved tilføjelse af kategorier: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    print("Sætter kategorier ind i databasen...")
    seed_categories()
    print("Kategorisåning afsluttet.")