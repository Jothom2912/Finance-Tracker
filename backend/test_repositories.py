#!/usr/bin/env python3
"""
Test script for verifying all repositories work correctly.
Tests that all repositories can be imported and instantiated.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.repositories import (
    get_transaction_repository,
    get_category_repository,
    get_account_repository,
    get_user_repository,
    get_budget_repository,
    get_goal_repository
)
from backend.config import ACTIVE_DB, DatabaseType

def test_repository_imports():
    """Test that all repositories can be imported and instantiated."""
    print("=" * 60)
    print("🧪 Testing Repository Imports")
    print("=" * 60)
    print(f"📊 Active Database: {ACTIVE_DB}\n")
    
    repositories = {
        "Transaction": get_transaction_repository,
        "Category": get_category_repository,
        "Account": get_account_repository,
        "User": get_user_repository,
        "Budget": get_budget_repository,
        "Goal": get_goal_repository,
    }
    
    results = {}
    
    for name, factory_func in repositories.items():
        try:
            repo = factory_func()
            repo_class = repo.__class__.__name__
            results[name] = {
                "status": "✅",
                "class": repo_class,
                "error": None
            }
            print(f"✅ {name:15} → {repo_class}")
        except Exception as e:
            results[name] = {
                "status": "❌",
                "class": None,
                "error": str(e)
            }
            print(f"❌ {name:15} → ERROR: {str(e)}")
    
    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("=" * 60)
    
    passed = sum(1 for r in results.values() if r["status"] == "✅")
    total = len(results)
    
    print(f"✅ Passed: {passed}/{total}")
    print(f"❌ Failed: {total - passed}/{total}")
    
    if passed == total:
        print("\n🎉 All repositories are working correctly!")
        return True
    else:
        print("\n⚠️  Some repositories failed. Check errors above.")
        return False

def test_repository_methods():
    """Test that repositories have the required methods."""
    print("\n" + "=" * 60)
    print("🔍 Testing Repository Methods")
    print("=" * 60)
    
    repositories = {
        "Transaction": get_transaction_repository(),
        "Category": get_category_repository(),
        "Account": get_account_repository(),
        "User": get_user_repository(),
        "Budget": get_budget_repository(),
        "Goal": get_goal_repository(),
    }
    
    # Define required methods for each repository type
    required_methods = {
        "Transaction": ["get_all", "get_by_id", "create", "update", "delete"],
        "Category": ["get_all", "get_by_id", "create", "update", "delete"],
        "Account": ["get_all", "get_by_id", "create", "update", "delete"],
        "User": ["get_all", "get_by_id", "get_by_username", "create"],
        "Budget": ["get_all", "get_by_id", "create", "update", "delete"],
        "Goal": ["get_all", "get_by_id", "create", "update", "delete"],
    }
    
    all_passed = True
    
    for name, repo in repositories.items():
        methods = required_methods.get(name, [])
        missing = []
        
        for method in methods:
            if not hasattr(repo, method):
                missing.append(method)
        
        if missing:
            print(f"❌ {name:15} → Missing methods: {', '.join(missing)}")
            all_passed = False
        else:
            print(f"✅ {name:15} → All methods present")
    
    if all_passed:
        print("\n🎉 All repositories have required methods!")
    else:
        print("\n⚠️  Some repositories are missing methods.")
    
    return all_passed

def test_database_connection():
    """Test if we can connect to the active database."""
    print("\n" + "=" * 60)
    print("🔌 Testing Database Connection")
    print("=" * 60)
    
    try:
        if ACTIVE_DB == DatabaseType.MYSQL.value:
            from backend.database.mysql import test_database_connection
            if test_database_connection():
                print("✅ MySQL connection successful")
                return True
            else:
                print("❌ MySQL connection failed")
                return False
        elif ACTIVE_DB == DatabaseType.ELASTICSEARCH.value:
            from backend.database.elasticsearch import get_es_client
            es = get_es_client()
            if es.ping():
                print("✅ Elasticsearch connection successful")
                return True
            else:
                print("❌ Elasticsearch connection failed")
                return False
        elif ACTIVE_DB == DatabaseType.NEO4J.value:
            from backend.database.neo4j import get_neo4j_driver
            driver = get_neo4j_driver()
            with driver.session() as session:
                result = session.run("RETURN 1 as test")
                if result.single():
                    print("✅ Neo4j connection successful")
                    return True
                else:
                    print("❌ Neo4j connection failed")
                    return False
        else:
            print(f"⚠️  Unknown database type: {ACTIVE_DB}")
            return False
    except Exception as e:
        print(f"❌ Connection error: {str(e)}")
        return False

if __name__ == "__main__":
    print("\n" + "🚀 Repository Test Suite" + "\n")
    
    # Run tests
    test1 = test_repository_imports()
    test2 = test_repository_methods()
    test3 = test_database_connection()
    
    print("\n" + "=" * 60)
    print("📋 Final Results")
    print("=" * 60)
    print(f"Repository Imports:  {'✅ PASS' if test1 else '❌ FAIL'}")
    print(f"Repository Methods:  {'✅ PASS' if test2 else '❌ FAIL'}")
    print(f"Database Connection: {'✅ PASS' if test3 else '❌ FAIL'}")
    
    if test1 and test2 and test3:
        print("\n🎉 All tests passed! Repositories are ready to use.")
        sys.exit(0)
    else:
        print("\n⚠️  Some tests failed. Check the output above.")
        sys.exit(1)

