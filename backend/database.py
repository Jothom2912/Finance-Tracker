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

# --- Model Definitioner ---
class TransactionType(enum.Enum):
    income = "income"
    expense = "expense"

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    type = Column(Enum(TransactionType), default=TransactionType.expense)

    transactions = relationship("Transaction", back_populates="category")

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    description = Column(String, index=True, nullable=True) # Jeg anbefaler nullable=True her, som du har
    amount = Column(Float)
    date = Column(Date)
    type = Column(Enum(TransactionType), default=TransactionType.expense)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True) 

    balance_after = Column(Float, nullable=True)
    currency = Column(String, default="DKK")
    sender = Column(String, nullable=True)
    recipient = Column(String, nullable=True)
    name = Column(String, nullable=True)

    category = relationship("Category", back_populates="transactions")

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