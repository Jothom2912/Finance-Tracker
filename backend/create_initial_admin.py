from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from passlib.context import CryptContext

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Database URL - Docker database
DATABASE_URL = "mysql+pymysql://root:123456@localhost:3307/finance_tracker"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def create_initial_admin():
    """Opret den første admin bruger direkte via SQL."""
    db = SessionLocal()
    try:
        # Tjek om admin eksisterer
        result = db.execute(text("SELECT * FROM User WHERE role = 'admin' LIMIT 1"))
        existing_admin = result.fetchone()
        
        if existing_admin:
            print("✓ Admin bruger eksisterer allerede")
            return
        
        # Hash password
        hashed_password = pwd_context.hash("Admin123!")
        
        # Indsæt admin bruger via raw SQL
        db.execute(
            text("""
                INSERT INTO User (username, password, email, role, is_active, created_at)
                VALUES (:username, :password, :email, :role, :is_active, NOW())
            """),
            {
                "username": "admin",
                "password": hashed_password,
                "email": "admin@financetracker.local",
                "role": "admin",
                "is_active": 1
            }
        )
        db.commit()
        
        print("=" * 50)
        print("✓ Initial admin bruger oprettet!")
        print("=" * 50)
        print("  Brugernavn: admin")
        print("  Password:   Admin123!")
        print("=" * 50)
        print("  ⚠ SKIFT PASSWORD MED DET SAMME!")
        print("=" * 50)
        
    except Exception as e:
        print(f"✗ Fejl ved oprettelse af admin bruger: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_initial_admin()