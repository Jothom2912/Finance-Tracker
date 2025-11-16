from sqlalchemy import create_engine, Column, Integer, String, Float, Date, Enum, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import enum
import os
from dotenv import load_dotenv

# --- Database Opsætning ---
load_dotenv() # Loader variabler fra .env filen
DATABASE_URL = os.getenv("DATABASE_URL") # Henter fra .env

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base() # Base-klasse for deklarative modeller

# Dependency til at få en database session
def get_db():
    db = SessionLocal()
    try:
        yield db # 'yield' gør dette til en generator, så sessionen kan bruges i FastAPI's Depends
    finally:
        db.close() # Sikrer at sessionen lukkes efter brug

# --- Enum Definitioner ---
class TransactionType(enum.Enum):
    income = "income"
    expense = "expense"

# --- Model Definitioner (matcher faktiske databasetabeller) ---

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True, nullable=False)
    type = Column(Enum(TransactionType), nullable=False)

    transactions = relationship("Transaction", back_populates="category")
    budgets = relationship("Budget", back_populates="category")

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    amount = Column(Float, nullable=False)
    description = Column(String(500), nullable=True, index=True)
    date = Column(Date, nullable=True)
    type = Column(Enum(TransactionType), nullable=False, default=TransactionType.expense)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    
    # Ekstra felter til banktransaktioner
    balance_after = Column(Float, nullable=True)
    currency = Column(String(10), default="DKK")
    sender = Column(String(255), nullable=True)
    recipient = Column(String(255), nullable=True)
    name = Column(String(255), nullable=True)

    category = relationship("Category", back_populates="transactions")

class Budget(Base):
    __tablename__ = "budgets"
    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    amount = Column(Float, nullable=False)
    month = Column(String(2), nullable=False)
    year = Column(String(4), nullable=False)

    category = relationship("Category", back_populates="budgets")


# --- Database Funktioner ---

# Funktion til at initialisere databasen (opretter tabeller)
def create_db_tables():
    # Ingen grund til at importere models her, da de er defineret i samme fil
    Base.metadata.create_all(bind=engine)
    print("Database tables checked/created.") # Tilføj en print-statement for feedback

# Valgfri: Funktion til at slette alle tabeller (BRUG MED FORSIGTIGHED!)
def drop_all_tables():
    # Ingen grund til at importere models her
    Base.metadata.drop_all(bind=engine)
    print("All tables dropped from database.")