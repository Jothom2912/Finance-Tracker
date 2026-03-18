"""Pytest root conftest — sets test env vars before any backend imports."""

import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest")
os.environ.setdefault("ACTIVE_DB", "mysql")
os.environ.setdefault("DATABASE_URL", "mysql+pymysql://test:test@localhost/test")
