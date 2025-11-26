# backend/models.py

from sqlalchemy import (
    Column, 
    Integer, 
    String, 
    Float, 
    Date, 
    DateTime, 
    Enum, 
    ForeignKey, 
    Table, 
    DECIMAL 
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
from .database import Base
import enum
from datetime import datetime

# ===== ENUMS =====
class TransactionType(enum.Enum):
    income = "income"
    expense = "expense"

# ===== JUNCTION TABLES =====
# Budget_has_Category junction table
budget_category_association = Table(
    'Budget_has_Category',
    Base.metadata,
    Column('Budget_idBudget', Integer, ForeignKey('Budget.idBudget', ondelete='CASCADE'), primary_key=True),
    Column('Category_idCategory', Integer, ForeignKey('Category.idCategory'), primary_key=True)
)

# AccountGroups_has_User junction table
account_group_user_association = Table(
    'AccountGroups_has_User',
    Base.metadata,
    Column('AccountGroups_idAccountGroups', Integer, ForeignKey('AccountGroups.idAccountGroups', ondelete='CASCADE'), primary_key=True),
    Column('User_idUser', Integer, ForeignKey('User.idUser', ondelete='CASCADE'), primary_key=True)
)

# ===== CORE MODELS =====

class User(Base):
    """Bruger model - Håndterer autentifikation og brugeroplysninger"""
    __tablename__ = "User"
    
    idUser = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(45), nullable=False, unique=True, index=True)
    password = Column(String(255), nullable=False)  # Hashed password
    email = Column(String(45), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    
    # Relationships
    accounts = relationship("Account", back_populates="user", cascade="all, delete-orphan")
    account_groups = relationship("AccountGroups", secondary=account_group_user_association, back_populates="users")
    
    def __repr__(self):
        return f"<User(idUser={self.idUser}, username='{self.username}')>"

class Category(Base):
    """Kategori model - Bruges til at kategorisere transaktioner"""
    __tablename__ = "Category"
    
    idCategory = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(45), nullable=False, unique=True, index=True)
    type = Column(String(45), nullable=False)  # f.eks. 'expense', 'income'
    
    # Relationships
    transactions = relationship("Transaction", back_populates="category")
    budgets = relationship("Budget", secondary=budget_category_association, back_populates="categories")
    
    def __repr__(self):
        return f"<Category(idCategory={self.idCategory}, name='{self.name}')>"

class Account(Base):
    """Konto model - Bruger kan have flere konti"""
    __tablename__ = "Account"
    
    idAccount = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(45), nullable=False)
    saldo = Column(DECIMAL(15, 2), default=0.00, nullable=False)
    User_idUser = Column(Integer, ForeignKey("User.idUser", ondelete="CASCADE"), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="accounts")
    transactions = relationship("Transaction", back_populates="account", cascade="all, delete-orphan")
    budgets = relationship("Budget", back_populates="account", cascade="all, delete-orphan")
    goals = relationship("Goal", back_populates="account", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Account(idAccount={self.idAccount}, name='{self.name}', saldo={self.saldo})>"

class Transaction(Base):
    """Transaktion model - Registrerer ind- og udgifter"""
    __tablename__ = "Transaction"
    
    idTransaction = Column(Integer, primary_key=True, autoincrement=True)
    amount = Column(DECIMAL(15, 2), nullable=False)
    description = Column(String(255), nullable=True, index=True)
    date = Column(DateTime, default=func.now(), nullable=False)
    type = Column(String(45), nullable=False)  # 'income' eller 'expense'
    Category_idCategory = Column(Integer, ForeignKey("Category.idCategory"), nullable=False)
    Account_idAccount = Column(Integer, ForeignKey("Account.idAccount", ondelete="CASCADE"), nullable=False)
    
    # Relationships
    category = relationship("Category", back_populates="transactions")
    account = relationship("Account", back_populates="transactions")
    planned_transaction = relationship("PlannedTransactions", back_populates="transaction", uselist=False)
    
    def __repr__(self):
        return f"<Transaction(idTransaction={self.idTransaction}, amount={self.amount}, type='{self.type}')>"

class Budget(Base):
    """Budget model - Bruges til at sætte budgetter per kategori"""
    __tablename__ = "Budget"
    
    idBudget = Column(Integer, primary_key=True, autoincrement=True)
    amount = Column(DECIMAL(15, 2), nullable=False)
    budget_date = Column(Date, nullable=True)
    Account_idAccount = Column(Integer, ForeignKey("Account.idAccount", ondelete="CASCADE"), nullable=False)
    
    # Relationships
    account = relationship("Account", back_populates="budgets")
    categories = relationship("Category", secondary=budget_category_association, back_populates="budgets")
    
    def __repr__(self):
        return f"<Budget(idBudget={self.idBudget}, amount={self.amount})>"

class Goal(Base):
    """Mål model - Bruges til at sætte sparemål"""
    __tablename__ = "Goal"
    
    idGoal = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(45), nullable=True)
    target_amount = Column(DECIMAL(15, 2), nullable=True)
    current_amount = Column(DECIMAL(15, 2), default=0.00, nullable=True)
    target_date = Column(Date, nullable=True)
    status = Column(String(45), nullable=True)
    Account_idAccount = Column(Integer, ForeignKey("Account.idAccount", ondelete="CASCADE"), nullable=False)
    
    # Relationships
    account = relationship("Account", back_populates="goals")
    
    def __repr__(self):
        return f"<Goal(idGoal={self.idGoal}, name='{self.name}', status='{self.status}')>"

class PlannedTransactions(Base):
    """Planlagte transaktioner - Bruges til at planlægge kommende transaktioner"""
    __tablename__ = "PlannedTransactions"
    
    idPlannedTransactions = Column(Integer, primary_key=True, autoincrement=True)
    Transaction_idTransaction = Column(Integer, ForeignKey("Transaction.idTransaction", ondelete="SET NULL"), nullable=True)
    name = Column(String(45), nullable=True)
    amount = Column(DECIMAL(15, 2), nullable=True)
    
    # Relationships
    transaction = relationship("Transaction", back_populates="planned_transaction")
    
    def __repr__(self):
        return f"<PlannedTransactions(idPlannedTransactions={self.idPlannedTransactions}, name='{self.name}')>"

class AccountGroups(Base):
    """Kontogruppe model - Bruges til at gruppere konti (f.eks. familiebudget)"""
    __tablename__ = "AccountGroups"
    
    idAccountGroups = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(45), nullable=True)
    
    # Relationships
    users = relationship("User", secondary=account_group_user_association, back_populates="account_groups")
    
    def __repr__(self):
        return f"<AccountGroups(idAccountGroups={self.idAccountGroups}, name='{self.name}')>"