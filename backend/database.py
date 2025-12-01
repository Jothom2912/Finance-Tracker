from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
from pathlib import Path

# --- Database Opsætning ---
dotenv_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=dotenv_path)
DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Importer Base fra base.py
from backend.models.base import Base

# Dependency til at få en database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Database Funktioner ---
def create_db_tables():
    # Importer alle models så de registreres
    from backend.models.user import User
    from backend.models.account import Account
    from backend.models.transaction import Transaction
    from backend.models.category import Category
    from backend.models.budget import Budget
    from backend.models.goal import Goal
    from backend.models.planned_transactions import PlannedTransactions
    from backend.models.account_groups import AccountGroups
    
    Base.metadata.create_all(bind=engine)
    print("Database tables checked/created.")

def drop_all_tables():
    Base.metadata.drop_all(bind=engine)
    print("All tables dropped from database.")