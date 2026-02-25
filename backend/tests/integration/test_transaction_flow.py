"""Integration tests for transaction flow."""
import pytest
import os
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from datetime import date
from decimal import Decimal
import io

# Force MySQL for tests - set ACTIVE_DB before importing anything that uses it
os.environ["ACTIVE_DB"] = "mysql"

from backend.main import app
from backend.database.mysql import Base, get_db
from backend.auth import create_access_token
from backend.models.mysql import (
    User, Account, Category, Budget, Transaction,
    TransactionType, budget_category_association
)


# === TEST DATABASE SETUP ===

@pytest.fixture(scope="function", autouse=True)
def set_mysql_for_tests(monkeypatch):
    """Force ACTIVE_DB to MySQL for all tests."""
    # Set environment variable
    monkeypatch.setenv("ACTIVE_DB", "mysql")
    
    # Also patch the config module if it's already imported
    import backend.config
    monkeypatch.setattr(backend.config, "ACTIVE_DB", "mysql")

@pytest.fixture(scope="function")
def mock_repositories(monkeypatch, test_db):
    """Mock repository factories to use MySQL with test_db session.
    
    Domain services use repository factories that are patched to the
    test session in this fixture.
    """
    from backend.repositories.mysql.category_repository import MySQLCategoryRepository
    from backend.repositories.mysql.transaction_repository import MySQLTransactionRepository
    from backend.repositories.mysql.account_repository import MySQLAccountRepository
    from backend.repositories.mysql.budget_repository import MySQLBudgetRepository
    from backend.repositories.mysql.user_repository import MySQLUserRepository
    from backend.repositories.mysql.planned_transaction_repository import MySQLPlannedTransactionRepository
    from backend.repositories.mysql.account_group_repository import MySQLAccountGroupRepository
    
    # Create repository instances with test_db
    cat_repo = MySQLCategoryRepository(db=test_db)
    trans_repo = MySQLTransactionRepository(db=test_db)
    acc_repo = MySQLAccountRepository(db=test_db)
    budget_repo = MySQLBudgetRepository(db=test_db)
    user_repo = MySQLUserRepository(db=test_db)
    pt_repo = MySQLPlannedTransactionRepository(db=test_db)
    ag_repo = MySQLAccountGroupRepository(db=test_db)
    
    # Repository factory mocks
    def get_cat_repo(db=None):
        return cat_repo
    def get_trans_repo(db=None):
        return trans_repo
    def get_acc_repo(db=None):
        return acc_repo
    def get_budget_repo(db=None):
        return budget_repo
    def get_user_repo(db=None):
        return user_repo
    def get_pt_repo(db=None):
        return pt_repo
    def get_ag_repo(db=None):
        return ag_repo
    
    # Patch repository factories
    monkeypatch.setattr("backend.repositories.get_category_repository", get_cat_repo)
    monkeypatch.setattr("backend.repositories.get_transaction_repository", get_trans_repo)
    monkeypatch.setattr("backend.repositories.get_account_repository", get_acc_repo)
    monkeypatch.setattr("backend.repositories.get_budget_repository", get_budget_repo)
    monkeypatch.setattr("backend.repositories.get_user_repository", get_user_repo)
    monkeypatch.setattr("backend.repositories.get_planned_transaction_repository", get_pt_repo)
    monkeypatch.setattr("backend.repositories.get_account_group_repository", get_ag_repo)
@pytest.fixture(scope="function")
def test_engine():
    """Opretter isoleret in-memory database per test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool  # Samme connection for alle threads
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def test_db(test_engine):
    """Database session med rollback efter test."""
    Session = sessionmaker(bind=test_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture(scope="function")
def test_client(test_engine, test_db):
    """FastAPI client med overridden database."""
    def override_get_db():
        # Return same session as test_db to ensure data consistency
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


# === TEST DATA FACTORIES ===

class Factory:
    """Simple factory for test data."""

    @staticmethod
    def user(db: Session, **kwargs) -> User:
        defaults = {"username": "testuser", "email": "test@test.com", "password": "hashed"}
        user = User(**{**defaults, **kwargs})
        db.add(user)
        db.commit()
        return user

    @staticmethod
    def account(db: Session, user_id: int, **kwargs) -> Account:
        defaults = {"name": "Test Account", "saldo": Decimal("0")}
        account = Account(User_idUser=user_id, **{**defaults, **kwargs})
        db.add(account)
        db.commit()
        return account

    @staticmethod
    def category(db: Session, name: str, type: str = "expense") -> Category:
        cat = Category(name=name, type=type)
        db.add(cat)
        db.flush()  # Flush to get ID
        db.commit()
        db.refresh(cat)  # Refresh to ensure all fields are loaded
        return cat

    @staticmethod
    def budget(db: Session, account_id: int, category_id: int, amount: Decimal) -> Budget:
        budget = Budget(
            amount=amount,
            budget_date=date.today().replace(day=1),
            Account_idAccount=account_id
        )
        db.add(budget)
        db.flush()
        db.execute(budget_category_association.insert().values(
            Budget_idBudget=budget.idBudget,
            Category_idCategory=category_id
        ))
        db.commit()
        return budget


# === INTEGRATION TESTS ===

class TestTransactionCreation:
    """Tests for manual transaction creation."""

    def test_create_transaction_updates_budget(self, test_client, test_db, mock_repositories):
        # Arrange
        user = Factory.user(test_db)
        account = Factory.account(test_db, user.idUser)
        category = Factory.category(test_db, "Mad")
        Factory.budget(test_db, account.idAccount, category.idCategory, Decimal("5000"))
        
        # Ensure test_db session is synchronized - flush and expire all to force refresh from DB
        test_db.flush()
        test_db.expire_all()
        
        # Verify category exists through repository (debug)
        from backend.repositories import get_category_repository
        category_repo = get_category_repository(test_db)  # ✅ FIX: Pass test_db session
        found_category = category_repo.get_by_id(category.idCategory)
        assert found_category is not None, f"Category {category.idCategory} should exist but was not found by repository"

        # Act
        token = create_access_token(user.idUser, user.username, user.email)
        response = test_client.post("/api/v1/transactions/",
            json={
                "category_id": category.idCategory,
                "account_id": account.idAccount,
                "amount": -500.0,
                "description": "Netto",
                "type": "expense",
                "date": date.today().isoformat()
            },
            headers={
                "Authorization": f"Bearer {token}",
                "X-Account-ID": str(account.idAccount),
            },
        )

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["description"] == "Netto"
        assert float(data["amount"]) == -500.0


class TestCsvUpload:
    """Tests for CSV upload functionality."""

    def test_csv_upload_creates_transactions(self, test_client, test_db, mock_repositories):
        # Arrange
        user = Factory.user(test_db)
        account = Factory.account(test_db, user.idUser)
        Factory.category(test_db, "Anden")  # Fallback kategori
        Factory.category(test_db, "madvarer/dagligvarer")
        Factory.category(test_db, "transport")
        
        # Ensure test_db session is synchronized - flush and expire all to force refresh from DB
        test_db.flush()
        test_db.expire_all()

        csv = b"""Bogf\xc3\xb8ringsdato;Bel\xc3\xb8b;Modtager;Afsender;Navn;Beskrivelse
2024/01/15;-150.50;Netto;;;Netto k\xc3\xb8b
2024/01/16;-75.00;DSB.dk/;;;DSB billet"""

        # Act
        token = create_access_token(user.idUser, user.username, user.email)
        response = test_client.post(
            "/api/v1/transactions/upload-csv/",
            files={"file": ("test.csv", io.BytesIO(csv), "text/csv")},
            headers={
                "Authorization": f"Bearer {token}",
                "X-Account-ID": str(account.idAccount),
            },
        )

        # Assert
        assert response.status_code == 200
        # Verificer response indeholder transaktioner
        response_data = response.json()
        assert isinstance(response_data, list)
        assert len(response_data) == 2
        
        # Verificer gennem repository (ikke direkte SQLAlchemy query)
        from backend.repositories import get_transaction_repository
        transaction_repo = get_transaction_repository(test_db)  # ✅ FIX: Pass test_db session
        transactions = transaction_repo.get_all(account_id=account.idAccount)
        assert len(transactions) == 2