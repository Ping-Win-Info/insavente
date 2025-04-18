# app/database.py
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
from pymongo.collection import Collection
from contextlib import contextmanager

from app.config.settings import settings

# Client MongoDB pour les tests (référence globale)
_test_client = None

# Base de données pour le mode asynchrone
async def get_database():
    client = AsyncIOMotorClient(settings.mongodb_url)
    try:
        yield client[settings.database_name]
    finally:
        client.close()

# Base de données pour les tests (synchrone)
def get_db():
    global _test_client
    
    # Si nous sommes en test, utilisons une connexion persistante
    if settings.database_name.endswith('_test'):
        if _test_client is None:
            _test_client = MongoClient(settings.mongodb_url)
        return _test_client[settings.database_name]
    
    # Sinon, créer une nouvelle connexion
    client = MongoClient(settings.mongodb_url)
    db = client[settings.database_name]
    return db
    # Note: Cette version retourne directement l'objet DB au lieu d'utiliser yield
    # Ce qui permet à la fonction get_test_db() de fonctionner correctement

# Pour la création des index (à exécuter une fois au démarrage)
def setup_mongodb_indexes():
    client = MongoClient(settings.mongodb_url)
    db = client[settings.database_name]
    
    # Créer un index de recherche textuelle sur les titres et descriptions
    db.items.create_index([("title", "text"), ("description", "text")])
    
    # Créer des index pour les filtres fréquents
    db.items.create_index("category")
    db.items.create_index("seller")
    db.items.create_index("price")
    db.items.create_index("created_at")
    
    # Créer des index pour les utilisateurs
    db.users.create_index("email", unique=True)
    db.users.create_index("phone_number")
    
    client.close()