# backend/models.py

from sqlalchemy import Column, Integer, String, Float, Date, Enum, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base # Vigtigt: Importer Base fra din database.py
import enum

class TransactionType(enum.Enum):
    income = "income"
    expense = "expense"

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    type = Column(Enum(TransactionType), default=TransactionType.expense)
    transactions = relationship("Transaction", back_populates="category")

class Budget(Base):
    __tablename__ = "budgets"

    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    amount = Column(Float, nullable=False)
    month = Column(String, nullable=False) # Store as 'MM' string
    year = Column(String, nullable=False) # Store as 'YYYY' string

    # Relationship to Category (assuming you have a Category model)
    category = relationship("Category") # Assumes a 'Category' model exists    

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    description = Column(String, index=True, nullable=True) # Sæt nullable til True, som du har
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