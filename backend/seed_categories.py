# backend/seed_categories.py
"""
Script til at seede kategorier i databasen.
Virker med alle 3 databaser (MySQL, Neo4j, Elasticsearch) baseret på ACTIVE_DB konfiguration.
"""
from backend.repositories import get_category_repository
from backend.services.categorization import category_rules
from backend.config import ACTIVE_DB


def determine_category_type(category_name: str) -> str:
    """Bestemmer om en kategori er 'expense' eller 'income' baseret på navnet."""
    category_lower = category_name.lower()
    
    # Income keywords
    income_keywords = [
        "indkomst",
        "løn",
        "støtte",
        "renter",
        "opsparing (ind)",
        "mobilepay ind",
        "betalinger fra andre",
    ]
    
    if any(keyword in category_lower for keyword in income_keywords):
        return "income"
    
    # Default er expense
    return "expense"


def seed_categories():
    """Seeder kategorier i den aktive database."""
    print(f"Seeder kategorier i {ACTIVE_DB.upper()}...")
    
    try:
        category_repo = get_category_repository()
        
        # Hent eksisterende kategorier
        existing_categories = category_repo.get_all()
        existing_names = {cat.get("name", "").lower() for cat in existing_categories}
        
        categories_to_add = []
        
        # Tilføj kategorier fra category_rules
        for category_name in set(category_rules.values()):
            if category_name.lower() not in existing_names:
                category_type = determine_category_type(category_name)
                categories_to_add.append({
                    "name": category_name,
                    "type": category_type
                })
        
        # Sørg for at "Anden" kategori findes (fallback kategori)
        if (
            "anden" not in existing_names
            and "anden" not in {cat.lower() for cat in set(category_rules.values())}
        ):
            categories_to_add.append({
                "name": "Anden",
                "type": "expense"
            })
        
        # Opret kategorier
        if categories_to_add:
            created_count = 0
            for category_data in categories_to_add:
                try:
                    category_repo.create(category_data)
                    created_count += 1
                    print(f"  [OK] Oprettet: {category_data['name']} ({category_data['type']})")
                except Exception as e:
                    print(f"  [WARNING] Fejl ved oprettelse af '{category_data['name']}': {e}")
            
            print(f"\n[SUCCESS] Tilfojet {created_count} nye kategorier til {ACTIVE_DB.upper()} databasen.")
        else:
            print(f"[INFO] Alle kategorier fra category_rules eksisterer allerede i {ACTIVE_DB.upper()} databasen.")
        
        # Vis samlet antal kategorier
        all_categories = category_repo.get_all()
        print(f"[INFO] Samlet antal kategorier i databasen: {len(all_categories)}")
        
    except Exception as e:
        print(f"[ERROR] Fejl ved seeding af kategorier: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    print("=" * 60)
    print("KATEGORI SEEDING SCRIPT")
    print("=" * 60)
    seed_categories()
    print("=" * 60)
    print("[SUCCESS] Kategorisaaning afsluttet.")
    print("=" * 60)
