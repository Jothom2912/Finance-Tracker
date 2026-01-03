-- ============================================================================
-- V1: Create database users with proper permissions
-- ============================================================================

-- Create the migration user (used by Flyway)
CREATE USER IF NOT EXISTS 'flyway_migrator'@'%' IDENTIFIED BY 'strong_flyway_password';
GRANT ALL PRIVILEGES ON finans_tracker.* TO 'flyway_migrator'@'%';

-- Create the application user (used by the backend)
CREATE USER IF NOT EXISTS 'finance_app'@'%' IDENTIFIED BY 'strong_app_password';
GRANT SELECT, INSERT, UPDATE, DELETE ON finans_tracker.* TO 'finance_app'@'%';

-- Apply privilege changes
FLUSH PRIVILEGES;
