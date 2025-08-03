# seed_categories.py
import os
from sqlalchemy.orm import Session # For type hint

# Ingen sys.path.insert() her!

# Importér moduler med den fulde pakke-sti
from backend.database import SessionLocal, engine, Base, create_db_tables, Category # Eller kun hvad der er nødvendigt, hvis modeller er i database.py
from backend.service.categorization import category_rules


# Sørg for at databasetabellerne er oprettet
create_db_tables()

def seed_categories():
    db: Session = SessionLocal()
    try:
        existing_categories = {cat.name.lower() for cat in db.query(Category).all()}

        categories_to_add = []
        for category_name in set(category_rules.values()):
            if category_name.lower() not in existing_categories:
                categories_to_add.append(Category(name=category_name))

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