"""
Shared fixtures for integration tests.

Provides:
- In-memory SQLite database per test
- Repository factory mocking (all repos use test_db)
- FastAPI TestClient with overridden DB dependency
- Factory class for creating test data
- Seed fixtures for common test scenarios (user, account, categories)
- Auth helpers (JWT login + headers)
"""

import pytest
import os
from decimal import Decimal
from datetime import date, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

# Force MySQL for tests - set ACTIVE_DB before importing anything that uses it
os.environ["ACTIVE_DB"] = "mysql"

from backend.main import app
from backend.database.mysql import Base
from backend.database import get_db
from backend.models.mysql import (
    User,
    Account,
    Category,
    Budget,
    Transaction,
    Goal,
    TransactionType,
    budget_category_association,
)


# ============================================================================
# Database & Environment
# ============================================================================


@pytest.fixture(scope="function", autouse=True)
def set_mysql_for_tests(monkeypatch):
    """Force ACTIVE_DB to MySQL for all tests."""
    monkeypatch.setenv("ACTIVE_DB", "mysql")
    import backend.config

    monkeypatch.setattr(backend.config, "ACTIVE_DB", "mysql")


@pytest.fixture(scope="function")
def test_engine():
    """In-memory SQLite database engine, created fresh per test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def test_db(test_engine):
    """Database session with rollback after each test."""
    TestingSession = sessionmaker(bind=test_engine)
    session = TestingSession()
    yield session
    session.rollback()
    session.close()


# ============================================================================
# Repository Mocking
# ============================================================================


@pytest.fixture(scope="function")
def mock_repositories(monkeypatch, test_db):
    """Patch all repository factories to use MySQL repos with test_db session."""
    from backend.repositories.mysql.category_repository import MySQLCategoryRepository
    from backend.repositories.mysql.transaction_repository import (
        MySQLTransactionRepository,
    )
    from backend.repositories.mysql.account_repository import MySQLAccountRepository
    from backend.repositories.mysql.budget_repository import MySQLBudgetRepository
    from backend.repositories.mysql.user_repository import MySQLUserRepository
    from backend.repositories.mysql.goal_repository import MySQLGoalRepository
    from backend.repositories.mysql.planned_transaction_repository import (
        MySQLPlannedTransactionRepository,
    )
    from backend.repositories.mysql.account_group_repository import (
        MySQLAccountGroupRepository,
    )

    # Create repository instances sharing the same test_db session
    cat_repo = MySQLCategoryRepository(db=test_db)
    trans_repo = MySQLTransactionRepository(db=test_db)
    acc_repo = MySQLAccountRepository(db=test_db)
    budget_repo = MySQLBudgetRepository(db=test_db)
    user_repo = MySQLUserRepository(db=test_db)
    goal_repo = MySQLGoalRepository(db=test_db)
    pt_repo = MySQLPlannedTransactionRepository(db=test_db)
    ag_repo = MySQLAccountGroupRepository(db=test_db)

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

    def get_goal_repo(db=None):
        return goal_repo

    def get_pt_repo(db=None):
        return pt_repo

    def get_ag_repo(db=None):
        return ag_repo

    # Patch in backend.repositories
    monkeypatch.setattr(
        "backend.repositories.get_category_repository", get_cat_repo
    )
    monkeypatch.setattr(
        "backend.repositories.get_transaction_repository", get_trans_repo
    )
    monkeypatch.setattr(
        "backend.repositories.get_account_repository", get_acc_repo
    )
    monkeypatch.setattr(
        "backend.repositories.get_budget_repository", get_budget_repo
    )
    monkeypatch.setattr(
        "backend.repositories.get_user_repository", get_user_repo
    )
    monkeypatch.setattr(
        "backend.repositories.get_goal_repository", get_goal_repo
    )
    monkeypatch.setattr(
        "backend.repositories.get_planned_transaction_repository", get_pt_repo
    )
    monkeypatch.setattr(
        "backend.repositories.get_account_group_repository", get_ag_repo
    )

# ============================================================================
# FastAPI Test Client
# ============================================================================


@pytest.fixture(scope="function")
def test_client(test_engine, test_db):
    """FastAPI test client with database dependency override."""

    def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


# ============================================================================
# Test Data Factory
# ============================================================================


class Factory:
    """Factory for creating test entities directly in the database."""

    @staticmethod
    def user(db: Session, **kwargs) -> User:
        from backend.auth import hash_password

        defaults = {
            "username": "testuser",
            "email": "test@test.com",
            "password": hash_password("testpassword123"),
        }
        user = User(**{**defaults, **kwargs})
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def account(db: Session, user_id: int, **kwargs) -> Account:
        defaults = {"name": "Test Account", "saldo": Decimal("0")}
        account = Account(User_idUser=user_id, **{**defaults, **kwargs})
        db.add(account)
        db.commit()
        db.refresh(account)
        return account

    @staticmethod
    def category(db: Session, name: str, cat_type: str = "expense") -> Category:
        cat = Category(name=name, type=cat_type)
        db.add(cat)
        db.flush()
        db.commit()
        db.refresh(cat)
        return cat

    @staticmethod
    def budget(
        db: Session, account_id: int, category_id: int, amount: Decimal
    ) -> Budget:
        budget = Budget(
            amount=amount,
            budget_date=date.today().replace(day=1),
            Account_idAccount=account_id,
        )
        db.add(budget)
        db.flush()
        db.execute(
            budget_category_association.insert().values(
                Budget_idBudget=budget.idBudget,
                Category_idCategory=category_id,
            )
        )
        db.commit()
        db.refresh(budget)
        return budget

    @staticmethod
    def goal(db: Session, account_id: int, **kwargs) -> Goal:
        defaults = {
            "name": "Test Goal",
            "target_amount": Decimal("10000"),
            "current_amount": Decimal("0"),
            "target_date": date.today() + timedelta(days=180),
            "status": "active",
        }
        goal = Goal(Account_idAccount=account_id, **{**defaults, **kwargs})
        db.add(goal)
        db.commit()
        db.refresh(goal)
        return goal

    @staticmethod
    def transaction(db: Session, account_id: int, category_id: int, **kwargs):
        defaults = {
            "amount": Decimal("-500"),
            "type": "expense",  # Use string, not enum (SQLite compat)
            "description": "Test transaction",
            "date": date.today(),
        }
        tx = Transaction(
            Account_idAccount=account_id,
            Category_idCategory=category_id,
            **{**defaults, **kwargs},
        )
        db.add(tx)
        db.commit()
        db.refresh(tx)
        return tx


# ============================================================================
# Seed Data Fixtures
# ============================================================================


@pytest.fixture
def seed_user(test_db):
    """Create a test user with a properly hashed password."""
    return Factory.user(test_db)


@pytest.fixture
def seed_account(test_db, seed_user):
    """Create a test account for the seed user."""
    return Factory.account(test_db, seed_user.idUser, name="Lønkonto", saldo=Decimal("10000"))


@pytest.fixture
def seed_categories(test_db):
    """Create standard expense and income categories."""
    return [
        Factory.category(test_db, "Mad", "expense"),
        Factory.category(test_db, "Transport", "expense"),
        Factory.category(test_db, "Løn", "income"),
    ]


# ============================================================================
# Auth Helpers
# ============================================================================


@pytest.fixture
def auth_headers(test_client, seed_user, mock_repositories):
    """Login the seed user and return Authorization headers with JWT token."""
    response = test_client.post(
        "/users/login",
        json={
            "username_or_email": seed_user.username,
            "password": "testpassword123",
        },
    )
    assert response.status_code == 200, f"Login failed: {response.json()}"
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def account_headers(auth_headers, seed_account):
    """Auth headers + X-Account-ID for routes that need both."""
    return {
        **auth_headers,
        "X-Account-ID": str(seed_account.idAccount),
    }
