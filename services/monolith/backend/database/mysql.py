# backend/database/mysql.py
"""
MySQL Database Connection
"""

import logging
import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from backend.config import DATABASE_URL

logger = logging.getLogger(__name__)

# Base kan oprettes uden DATABASE_URL (bruges i tests)
Base = declarative_base()

# Check if we're running in pytest or CI environment (tests don't need real DATABASE_URL)
import inspect
import sys


def _is_test_environment():
    """Check if we're running in a test environment"""
    # Check environment variables set by pytest
    if "PYTEST_CURRENT_TEST" in os.environ:
        return True

    # Check if pytest is in sys.modules
    if "pytest" in sys.modules:
        return True

    # Check if we're being imported from a test file by examining the call stack
    try:
        stack = inspect.stack()
        for frame_info in stack:
            filename = frame_info.filename
            if filename and ("test" in filename.lower() or "pytest" in filename.lower()):
                return True
    except Exception:
        pass

    # Check command line arguments
    if any("pytest" in str(arg).lower() for arg in sys.argv):
        return True

    return False


_is_pytest = _is_test_environment()

# Valider DATABASE_URL kun hvis vi IKKE er i pytest
# I pytest miljøer bruger tests deres egen in-memory database
if not DATABASE_URL and not _is_pytest:
    logger.error("❌ DATABASE_URL not found in environment!")
    raise ValueError("DATABASE_URL must be set in .env file")

# Opret engine og SessionLocal kun hvis DATABASE_URL er sat
# I pytest miljøer vil disse være None, men det er OK fordi tests bruger deres egen database
if DATABASE_URL:
    logger.info(f"🔗 Database URL: {DATABASE_URL.split('@')[0]}@***")  # Log uden password

    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        echo=False,
        connect_args={
            "connect_timeout": 10,  # Øget til 10 sekunder
        },
        pool_timeout=10,
        pool_size=5,
        max_overflow=10,
        pool_recycle=3600,
    )

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
else:
    # I pytest miljøer, sæt disse til None
    # Tests vil override get_db() dependency alligevel
    engine = None
    SessionLocal = None


def get_db():
    """Dependency til at få en database session"""
    if SessionLocal is None:
        raise RuntimeError("Database not initialized. DATABASE_URL must be set in .env file")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_database_connection():
    """
    Test database connection uden at oprette tabeller.
    Returns: (success: bool, error_message: str)
    """
    if engine is None:
        return False, "Database not initialized. DATABASE_URL must be set in .env file"
    try:
        logger.info("🔍 Tester database forbindelse...")
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1 as test"))
            test_value = result.fetchone()
            if test_value and test_value[0] == 1:
                logger.info("✅ Database forbindelse OK")
                return True, None
    except Exception as e:
        error_msg = f"Database connection failed: {str(e)}"
        logger.error(f"❌ {error_msg}")
        return False, error_msg


def create_db_tables():
    """
    Opretter databasetabeller med robust error handling.
    Returnerer True hvis success, False hvis fejl.
    """
    try:
        logger.info("=" * 60)
        logger.info("📋 STARTER DATABASE TABLE CREATION")
        logger.info("=" * 60)

        # Step 1: Test connection først
        success, error = test_database_connection()
        if not success:
            logger.warning(f"⚠️ Database ikke tilgængelig: {error}")
            logger.warning("⚠️ Springer table creation over - vil prøve igen ved første request")
            return False

        # Step 2: Import models
        logger.info("📦 Importerer models...")
        try:
            from backend.models.mysql import (  # noqa: F401
                account,
                account_groups,
                bank_connection,
                budget,
                category,
                goal,
                merchant,
                monthly_budget,
                planned_transactions,
                subcategory,
                transaction,
                user,
            )

            logger.info("✅ Alle models importeret succesfuldt")
        except ImportError as e:
            logger.error(f"❌ Fejl ved import af models: {e}")
            import traceback

            logger.error(traceback.format_exc())
            return False

        # Step 3: Opret tabeller
        if engine is None:
            logger.warning("⚠️ Database engine not initialized - skipping table creation")
            return False

        logger.info("🏗️  Opretter/tjekker tabeller...")
        Base.metadata.create_all(bind=engine)

        # Step 4: Verificer at tabeller blev oprettet
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE()")
            )
            table_count = result.fetchone()[0]
            logger.info(f"✅ Database indeholder {table_count} tabeller")

        logger.info("=" * 60)
        logger.info("✅ DATABASE TABLE CREATION COMPLETED")
        logger.info("=" * 60)
        return True

    except Exception as e:
        logger.error("=" * 60)
        logger.error("❌ FEJL VED DATABASE TABLE CREATION")
        logger.error("=" * 60)
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error message: {str(e)}")
        import traceback

        logger.error(traceback.format_exc())
        logger.warning("⚠️ Backend vil fortsætte, men database er muligvis ikke tilgængelig")
        return False


def drop_all_tables():
    """Sletter alle tabeller - BRUG MED FORSIGTIGHED!"""
    if engine is None:
        raise RuntimeError("Database not initialized. DATABASE_URL must be set in .env file")
    logger.warning("⚠️ DROPPING ALL TABLES - THIS WILL DELETE ALL DATA!")
    try:
        Base.metadata.drop_all(bind=engine)
        logger.info("✅ All tables dropped from database")
    except Exception as e:
        logger.error(f"❌ Error dropping tables: {e}")
        raise
