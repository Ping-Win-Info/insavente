# tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient
from bson import ObjectId

from app.main import app
from app.config.settings import settings

# Client de base de données partagé pour tous les tests
_test_client = None

@pytest.fixture(scope="session")
def client():
    """Fixture pour créer un client de test FastAPI"""
    return TestClient(app)

def get_mongo_client():
    """Retourne une référence partagée au client MongoDB"""
    global _test_client
    if _test_client is None:
        _test_client = MongoClient(settings.mongodb_url)
    return _test_client

@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Configure une base de données de test et nettoie après les tests"""
    # Utiliser une base de données de test
    settings.database_name = f"{settings.database_name}_test"
    
    # Obtenir le client MongoDB
    client = get_mongo_client()
    
    # S'assurer que la base de données est propre avant de commencer
    client.drop_database(settings.database_name)
    
    # Configurer les index
    db = client[settings.database_name]
    db.items.create_index([("title", "text"), ("description", "text")])
    db.items.create_index("category")
    db.items.create_index("seller")
    db.items.create_index("price")
    db.items.create_index("created_at")
    
    yield
    
    # Nettoyer après les tests
    client.drop_database(settings.database_name)
    # Ne PAS fermer le client ici, nous le gardons ouvert pour tous les tests