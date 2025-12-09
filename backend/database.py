from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# --- Database Opsætning ---
load_dotenv() # Loader variabler fra .env filen
DATABASE_URL = os.getenv("DATABASE_URL") # Henter fra .env

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Tjekker forbindelser før brug
    echo=False  # Sæt til True for at se SQL queries i console
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base() # Base-klasse for deklarative modeller

# Dependency til at få en database session
def get_db():
    db = SessionLocal()
    try:
        yield db # 'yield' gør dette til en generator, så sessionen kan bruges i FastAPI's Depends
    finally:
        db.close() # Sikrer at sessionen lukkes efter brug

# --- Database Funktioner ---

# Funktion til at initialisere databasen (opretter tabeller)
def create_db_tables():
    # Import alle models fra models package så de bliver registreret
    from . import models
    Base.metadata.create_all(bind=engine)
    print("Database tables checked/created.") # Tilføj en print-statement for feedback

# Valgfri: Funktion til at slette alle tabeller (BRUG MED FORSIGTIGHED!)
def drop_all_tables():
    # Import alle models fra models package
    from . import models
    Base.metadata.drop_all(bind=engine)
    print("All tables dropped from database.")