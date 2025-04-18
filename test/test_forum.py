# tests/test_forum.py
import pytest
from fastapi.testclient import TestClient
from bson import ObjectId
from datetime import datetime
import jwt

from app.main import app
from app.config.settings import settings
from app.database import get_db

client = TestClient(app)

# Référence globale à la connexion de base de données
test_db = None

# Fonction pour obtenir la base de données de test
def get_test_db():
    global test_db
    if test_db is None:
        test_db = get_db()
    return test_db

# Fixture pour créer un token de test
@pytest.fixture
def test_token():
    test_user_id = str(ObjectId())
    token = jwt.encode(
        {"sub": test_user_id, "exp": datetime.utcnow().timestamp() + 3600},
        settings.jwt_secret
    )
    return token, test_user_id

# Fixture pour nettoyer la base de données après les tests
@pytest.fixture(autouse=True)
def cleanup_db():
    yield
    db = get_test_db()
    db.users.delete_many({})
    db.forum_categories.delete_many({})
    db.forum_threads.delete_many({})
    db.forum_posts.delete_many({})

# Fixture pour créer des catégories de forum
@pytest.fixture
def create_forum_categories():
    db = get_test_db()
    categories = [
        {
            "_id": ObjectId(),
            "name": "Général",
            "description": "Discussions générales sur le site",
            "order": 1
        },
        {
            "_id": ObjectId(),
            "name": "Achat/Vente",
            "description": "Conseils pour acheter et vendre",
            "order": 2
        },
        {
            "_id": ObjectId(),
            "name": "Support",
            "description": "Aide et support technique",
            "order": 3
        }
    ]
    db.forum_categories.insert_many(categories)
    return [str(cat["_id"]) for cat in categories], [cat["name"] for cat in categories]

class TestForum:
    
    def test_get_forum_categories(self, create_forum_categories):
        """Test pour récupérer les catégories du forum"""
        category_ids, category_names = create_forum_categories
        
        response = client.get("/api/forum/categories")
        
        assert response.status_code == 200
        data = response.json()
        assert "categories" in data
        assert len(data["categories"]) == len(category_ids)
        
        # Vérifier que les catégories sont triées par ordre
        assert data["categories"][0]["name"] == "Général"
        assert data["categories"][1]["name"] == "Achat/Vente"
        assert data["categories"][2]["name"] == "Support"
        
        # Vérifier les détails des catégories
        for category in data["categories"]:
            assert "id" in category
            assert "name" in category
            assert "description" in category
            assert "order" in category
    
    def test_create_thread(self, test_token, create_forum_categories):
        """Test pour créer un nouveau sujet dans le forum"""
        token, user_id = test_token
        category_ids, _ = create_forum_categories
        
        thread_data = {
            "title": "Nouveau sujet de discussion",
            "content": "Contenu du premier message du sujet",
            "category_id": category_ids[0]
        }
        
        response = client.post(
            "/api/forum/threads",
            json=thread_data,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == thread_data["title"]
        assert data["author_id"] == user_id
        assert data["category_id"] == category_ids[0]
        assert "created_at" in data
        assert "post_count" in data
        assert data["post_count"] == 1
        
        # Vérifier qu'un premier post a été créé
        assert "first_post" in data
        assert data["first_post"]["content"] == thread_data["content"]
        assert data["first_post"]["author_id"] == user_id
    
    def test_create_thread_invalid_category(self, test_token):
        """Test pour créer un sujet dans une catégorie inexistante"""
        token, _ = test_token
        
        thread_data = {
            "title": "Nouveau sujet de discussion",
            "content": "Contenu du premier message du sujet",
            "category_id": str(ObjectId())  # ID de catégorie inexistante
        }
        
        response = client.post(
            "/api/forum/threads",
            json=thread_data,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 404
        assert "Catégorie non trouvée" in response.json()["detail"]
    
    def test_get_threads_by_category(self, test_token, create_forum_categories):
        """Test pour récupérer les sujets d'une catégorie"""
        token, user_id = test_token
        category_ids, _ = create_forum_categories
        
        # Créer quelques sujets dans différentes catégories
        db = get_test_db()
        threads = [
            {
                "_id": ObjectId(),
                "title": "Sujet 1 dans Général",
                "author_id": user_id,
                "category_id": category_ids[0],
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "post_count": 1,
                "is_pinned": False,
                "is_locked": False
            },
            {
                "_id": ObjectId(),
                "title": "Sujet 2 dans Général",
                "author_id": user_id,
                "category_id": category_ids[0],
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "post_count": 3,
                "is_pinned": True,  # Sujet épinglé
                "is_locked": False
            },
            {
                "_id": ObjectId(),
                "title": "Sujet dans Achat/Vente",
                "author_id": user_id,
                "category_id": category_ids[1],
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "post_count": 1,
                "is_pinned": False,
                "is_locked": False
            }
        ]
        db.forum_threads.insert_many(threads)
        
        # Récupérer les sujets de la catégorie Général
        response = client.get(f"/api/forum/threads?category_id={category_ids[0]}")
        
        assert response.status_code == 200
        data = response.json()
        assert "threads" in data
        assert len(data["threads"]) == 2
        
        # Vérifier que les sujets épinglés sont en premier
        assert data["threads"][0]["title"] == "Sujet 2 dans Général"
        assert data["threads"][0]["is_pinned"] is True
        
        # Récupérer les sujets sans filtre de catégorie
        response = client.get("/api/forum/threads")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["threads"]) == 3
    
    def test_get_thread_with_posts(self, test_token, create_forum_categories):
        """Test pour récupérer un sujet avec ses messages"""
        token, user_id = test_token
        category_ids, _ = create_forum_categories
        
        # Créer un sujet avec plusieurs messages
        db = get_test_db()
        thread_id = ObjectId()
        
        db.forum_threads.insert_one({
            "_id": thread_id,
            "title": "Sujet de discussion",
            "author_id": user_id,
            "category_id": category_ids[0],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "post_count": 3,
            "is_pinned": False,
            "is_locked": False
        })
        
        # Créer des messages dans ce sujet
        db.forum_posts.insert_many([
            {
                "_id": ObjectId(),
                "thread_id": str(thread_id),
                "author_id": user_id,
                "content": "Premier message du sujet",
                "created_at": datetime.utcnow(),
                "updated_at": None
            },
            {
                "_id": ObjectId(),
                "thread_id": str(thread_id),
                "author_id": str(ObjectId()),  # Autre utilisateur
                "content": "Réponse d'un autre utilisateur",
                "created_at": datetime.utcnow(),
                "updated_at": None
            },
            {
                "_id": ObjectId(),
                "thread_id": str(thread_id),
                "author_id": user_id,
                "content": "Réponse de l'auteur original",
                "created_at": datetime.utcnow(),
                "updated_at": None
            }
        ])
        
        response = client.get(f"/api/forum/threads/{str(thread_id)}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(thread_id)
        assert data["title"] == "Sujet de discussion"
        assert "posts" in data
        assert len(data["posts"]) == 3
        
        # Vérifier les détails des messages
        for post in data["posts"]:
            assert "id" in post
            assert "author_id" in post
            assert "content" in post
            assert "created_at" in post
            assert "thread_id" in post
            assert post["thread_id"] == str(thread_id)
    
    def test_add_post_to_thread(self, test_token, create_forum_categories):
        """Test pour ajouter un message à un sujet existant"""
        token, user_id = test_token
        category_ids, _ = create_forum_categories
        
        # Créer un sujet
        db = get_test_db()
        thread_id = ObjectId()
        
        db.forum_threads.insert_one({
            "_id": thread_id,
            "title": "Sujet de discussion",
            "author_id": user_id,
            "category_id": category_ids[0],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "post_count": 1,
            "is_pinned": False,
            "is_locked": False
        })
        
        # Créer le premier message du sujet
        db.forum_posts.insert_one({
            "_id": ObjectId(),
            "thread_id": str(thread_id),
            "author_id": user_id,
            "content": "Premier message du sujet",
            "created_at": datetime.utcnow(),
            "updated_at": None
        })
        
        # Ajouter un nouveau message au sujet
        post_data = {
            "content": "Voici ma réponse au sujet"
        }
        
        response = client.post(
            f"/api/forum/threads/{str(thread_id)}/posts",
            json=post_data,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["content"] == post_data["content"]
        assert data["author_id"] == user_id
        assert data["thread_id"] == str(thread_id)
        
        # Vérifier que le compteur de messages du sujet a été incrémenté
        thread = db.forum_threads.find_one({"_id": thread_id})
        assert thread["post_count"] == 2
        assert thread["updated_at"] > thread["created_at"]
    
    def test_add_post_to_locked_thread(self, test_token, create_forum_categories):
        """Test pour vérifier qu'on ne peut pas ajouter un message à un sujet verrouillé"""
        token, user_id = test_token
        category_ids, _ = create_forum_categories
        
        # Créer un sujet verrouillé
        db = get_test_db()
        thread_id = ObjectId()
        
        db.forum_threads.insert_one({
            "_id": thread_id,
            "title": "Sujet verrouillé",
            "author_id": user_id,
            "category_id": category_ids[0],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "post_count": 1,
            "is_pinned": False,
            "is_locked": True  # Sujet verrouillé
        })
        
        # Créer le premier message du sujet
        db.forum_posts.insert_one({
            "_id": ObjectId(),
            "thread_id": str(thread_id),
            "author_id": user_id,
            "content": "Premier message du sujet",
            "created_at": datetime.utcnow(),
            "updated_at": None
        })
        
        # Tenter d'ajouter un nouveau message
        post_data = {
            "content": "Voici ma réponse au sujet"
        }
        
        response = client.post(
            f"/api/forum/threads/{str(thread_id)}/posts",
            json=post_data,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 403
        assert "Ce sujet est verrouillé" in response.json()["detail"]
    
    def test_search_threads(self, test_token, create_forum_categories):
        """Test pour rechercher des sujets par mot-clé"""
        token, user_id = test_token
        category_ids, _ = create_forum_categories
        
        # Créer quelques sujets avec des titres différents
        db = get_test_db()
        threads = [
            {
                "_id": ObjectId(),
                "title": "Comment vendre efficacement",
                "author_id": user_id,
                "category_id": category_ids[1],  # Achat/Vente
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "post_count": 1,
                "is_pinned": False,
                "is_locked": False
            },
            {
                "_id": ObjectId(),
                "title": "Astuces pour acheter à bon prix",
                "author_id": user_id,
                "category_id": category_ids[1],  # Achat/Vente
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "post_count": 1,
                "is_pinned": False,
                "is_locked": False
            },
            {
                "_id": ObjectId(),
                "title": "Problème avec mon compte",
                "author_id": user_id,
                "category_id": category_ids[2],  # Support
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "post_count": 1,
                "is_pinned": False,
                "is_locked": False
            }
        ]
        db.forum_threads.insert_many(threads)
        
        # Rechercher par le terme "acheter"
        response = client.get("/api/forum/threads?search=acheter")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["threads"]) == 1
        assert "Astuces pour acheter" in data["threads"][0]["title"]
        
        # Rechercher par le terme "vendre"
        response = client.get("/api/forum/threads?search=vendre")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["threads"]) == 1
        assert "Comment vendre" in data["threads"][0]["title"]
        
        # Rechercher par catégorie et terme
        response = client.get(f"/api/forum/threads?category_id={category_ids[1]}&search=acheter")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["threads"]) == 1
        assert "Astuces pour acheter" in data["threads"][0]["title"]
    
    def test_lock_thread_as_admin(self, test_token, create_forum_categories):
        """Test pour verrouiller un sujet (action réservée aux administrateurs)"""
        token, user_id = test_token
        category_ids, _ = create_forum_categories
        
        # Créer un utilisateur avec des droits d'administrateur
        db = get_test_db()
        db.users.insert_one({
            "_id": ObjectId(user_id),
            "email": "admin@example.com",
            "hashed_password": "hashed_password_here",
            "full_name": "Admin User",
            "phone_number": "+33612345678",
            "is_active": True,
            "is_admin": True,  # Assurez-vous que cette valeur est définie
            "created_at": datetime.utcnow()
        })
        
        # Créer un sujet
        thread_id = ObjectId()
        db.forum_threads.insert_one({
            "_id": thread_id,
            "title": "Sujet à verrouiller",
            "author_id": str(ObjectId()),  # Un autre utilisateur est l'auteur
            "category_id": category_ids[0],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "post_count": 1,
            "is_pinned": False,
            "is_locked": False
        })
        
        # Verrouiller le sujet
        lock_data = {
            "is_locked": True
        }
        
        response = client.put(
            f"/api/forum/threads/{str(thread_id)}/lock",
            json=lock_data,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["is_locked"] is True
        
        # Vérifier que le sujet est bien verrouillé dans la base de données
        thread = db.forum_threads.find_one({"_id": thread_id})
        assert thread["is_locked"] is True
    
    def test_lock_thread_as_regular_user(self, test_token, create_forum_categories):
        """Test pour vérifier qu'un utilisateur normal ne peut pas verrouiller un sujet"""
        token, user_id = test_token
        category_ids, _ = create_forum_categories
        
        # Créer un sujet
        db = get_test_db()
        thread_id = ObjectId()
        db.forum_threads.insert_one({
            "_id": thread_id,
            "title": "Sujet à verrouiller",
            "author_id": str(ObjectId()),  # Un autre utilisateur est l'auteur
            "category_id": category_ids[0],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "post_count": 1,
            "is_pinned": False,
            "is_locked": False
        })
        
        # Tenter de verrouiller le sujet
        lock_data = {
            "is_locked": True
        }
        
        response = client.put(
            f"/api/forum/threads/{str(thread_id)}/lock",
            json=lock_data,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 403
        assert "Droits d'administrateur requis" in response.json()["detail"]