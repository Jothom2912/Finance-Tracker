# backend/database/mysql.py
"""
MySQL Database Connection
"""
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

# --- Database Opsætning ---
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# Valider DATABASE_URL
if not DATABASE_URL:
    logger.error("❌ DATABASE_URL not found in environment!")
    raise ValueError("DATABASE_URL must be set in .env file")

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
Base = declarative_base()

def get_db():
    """Dependency til at få en database session"""
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
            from backend.models.mysql import (
                transaction,
                account,
                category,
                user,
                budget,
                goal,
                account_groups,
                planned_transactions
            )
            logger.info("✅ Alle models importeret succesfuldt")
        except ImportError as e:
            logger.error(f"❌ Fejl ved import af models: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
        
        # Step 3: Opret tabeller
        logger.info("🏗️  Opretter/tjekker tabeller...")
        Base.metadata.create_all(bind=engine)
        
        # Step 4: Verificer at tabeller blev oprettet
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = DATABASE()"
            ))
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
    logger.warning("⚠️ DROPPING ALL TABLES - THIS WILL DELETE ALL DATA!")
    try:
        from backend.models.mysql import (
            transaction, account, category, user, budget, goal,
            account_groups, planned_transactions
        )
        Base.metadata.drop_all(bind=engine)
        logger.info("✅ All tables dropped from database")
    except Exception as e:
        logger.error(f"❌ Error dropping tables: {e}")
        raise
