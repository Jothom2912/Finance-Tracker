# backend/migrations/mysql/add_created_at_to_transactions.py
"""
Migration script to add created_at column to Transaction table.

This script adds a created_at timestamp column to the Transaction table
if it doesn't already exist. For existing transactions without created_at,
it will set created_at to the transaction date or current timestamp.

Usage:
    python -m backend.migrations.mysql.add_created_at_to_transactions
"""
from sqlalchemy import text
from backend.database.mysql import engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_created_at_column():
    """Add created_at column to Transaction table if it doesn't exist."""
    logger.info("=" * 60)
    logger.info("🔄 STARTER MIGRATION: Add created_at to Transaction table")
    logger.info("=" * 60)
    
    if engine is None:
        logger.error("❌ Database engine not initialized")
        return False
    
    try:
        # Check if column already exists
        logger.info("🔍 Checking if created_at column exists...")
        with engine.begin() as conn:  # begin() auto-commits
            result = conn.execute(text("""
                SELECT COUNT(*) 
                FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = 'Transaction'
                AND COLUMN_NAME = 'created_at'
            """))
            column_exists = result.fetchone()[0] > 0
        
        if column_exists:
            logger.info("✅ created_at column already exists - skipping migration")
            return True
        
        # Add the column
        logger.info("📝 Adding created_at column to Transaction table...")
        logger.info("   (Dette kan tage lidt tid hvis der er mange transaktioner...)")
        
        with engine.begin() as conn:  # begin() auto-commits
            # Add column as nullable first to avoid lock issues
            conn.execute(text("""
                ALTER TABLE Transaction 
                ADD COLUMN created_at DATETIME NULL
            """))
            logger.info("   ✓ Kolonne tilføjet (nullable)")
        
        # Update existing rows
        logger.info("🔄 Updating existing transactions...")
        with engine.begin() as conn:
            result = conn.execute(text("""
                UPDATE Transaction 
                SET created_at = COALESCE(date, CURRENT_TIMESTAMP)
                WHERE created_at IS NULL
            """))
            updated_count = result.rowcount
            logger.info(f"   ✓ Opdateret {updated_count} eksisterende transaktioner")
        
        # Make column NOT NULL
        logger.info("🔒 Making created_at NOT NULL...")
        with engine.begin() as conn:
            conn.execute(text("""
                ALTER TABLE Transaction 
                MODIFY COLUMN created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            """))
            logger.info("   ✓ Kolonne er nu NOT NULL")
        
        # Verify the column was created successfully
        logger.info("🔍 Verificerer at kolonnen er oprettet korrekt...")
        with engine.begin() as conn:
            result = conn.execute(text("""
                SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT
                FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = 'Transaction'
                AND COLUMN_NAME = 'created_at'
            """))
            column_info = result.fetchone()
            if column_info:
                logger.info(f"   ✓ Kolonne fundet: {column_info[0]} ({column_info[1]}, NULLABLE={column_info[2]}, DEFAULT={column_info[3]})")
            else:
                logger.warning("   ⚠ Kolonne ikke fundet efter migration!")
        
        logger.info("=" * 60)
        logger.info("✅ MIGRATION FULDFØRT!")
        logger.info("=" * 60)
        return True
        
    except Exception as e:
        logger.error(f"❌ Fejl ved migration: {e}")
        import traceback
        logger.error(traceback.format_exc())
        # Check if column exists anyway (might have been created before error)
        try:
            with engine.begin() as conn:
                result = conn.execute(text("""
                    SELECT COUNT(*) 
                    FROM information_schema.COLUMNS 
                    WHERE TABLE_SCHEMA = DATABASE()
                    AND TABLE_NAME = 'Transaction'
                    AND COLUMN_NAME = 'created_at'
                """))
                if result.fetchone()[0] > 0:
                    logger.info("⚠️ Men kolonnen eksisterer alligevel - migration kan være delvist gennemført")
        except:
            pass
        return False

if __name__ == "__main__":
    success = add_created_at_column()
    exit(0 if success else 1)

