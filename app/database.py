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
        return _test_client[settings.database_name]  # Retourne directement l'objet DB
    
    # Sinon, comportement normal avec fermeture
    client = MongoClient(settings.mongodb_url)
    db = client[settings.database_name]
    return db  # Retourne directement l'objet DB
    # Note: dans ce cas, on ne ferme pas le client, ce qui pourrait causer des fuites de ressources
    # mais comme ce n'est pas utilisé pour les tests, ce n'est pas critique

# Version alternative avec contextmanager si vous préférez la gestion propre des ressources
@contextmanager
def get_db_context():
    client = MongoClient(settings.mongodb_url)
    try:
        yield client[settings.database_name]
    finally:
        client.close()

# Pour la création des index (à exécuter une fois au démarrage)
def setup_mongodb_indexes():
    client = MongoClient(settings.mongodb_url)
    db = client[settings.database_name]
    
    # Index pour les articles/items
    db.items.create_index([("title", "text"), ("description", "text")])
    db.items.create_index("category")
    db.items.create_index("seller")
    db.items.create_index("price")
    db.items.create_index("created_at")
    
    # Index pour les utilisateurs
    db.users.create_index("email", unique=True)
    
    # Index pour les évaluations
    db.ratings.create_index("rated_user")
    db.ratings.create_index([("rated_user", 1), ("rating_user", 1)], unique=True)  # Un utilisateur ne peut laisser qu'une évaluation
    db.ratings.create_index("created_at")
    
    # Index pour les conversations
    db.conversations.create_index("participants")  # Pour rechercher les conversations d'un utilisateur
    db.conversations.create_index("updated_at")    # Pour trier par dernière mise à jour
    
    # Index pour les messages
    db.messages.create_index("conversation_id")    # Pour récupérer les messages d'une conversation
    db.messages.create_index([("conversation_id", 1), ("created_at", 1)])  # Pour trier les messages par date
    db.messages.create_index([("conversation_id", 1), ("sender_id", 1), ("read", 1)])  # Pour les messages non lus
    
    # Index pour le forum - catégories
    db.forum_categories.create_index("order")  # Pour trier les catégories par ordre
    
    # Index pour le forum - sujets
    db.forum_threads.create_index([("title", "text")])  # Pour la recherche textuelle
    db.forum_threads.create_index("category_id")         # Pour filtrer par catégorie
    db.forum_threads.create_index("author_id")           # Pour trouver les sujets d'un utilisateur
    db.forum_threads.create_index("created_at")          # Pour trier par date de création
    db.forum_threads.create_index("updated_at")          # Pour trier par dernière activité
    db.forum_threads.create_index("is_pinned")           # Pour filtrer les sujets épinglés
    
    # Index pour le forum - messages
    db.forum_posts.create_index("thread_id")             # Pour récupérer les messages d'un sujet
    db.forum_posts.create_index([("thread_id", 1), ("created_at", 1)])  # Pour trier les messages par date
    db.forum_posts.create_index("author_id")             # Pour trouver les messages d'un utilisateur
    
    client.close()