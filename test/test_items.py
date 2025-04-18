# tests/test_items.py
import pytest
from fastapi.testclient import TestClient
from bson import ObjectId
from datetime import datetime
import jwt

from app.main import app
from app.models.item import ItemModel
from app.config.settings import settings
from app.database import get_db

client = TestClient(app)

# Référence globale à la connexion de base de données
test_db = None

# Fonction pour obtenir la base de données de test
def get_test_db():
    global test_db
    if test_db is None:
        # Maintenant, get_db() retourne directement un objet db
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
    db.items.delete_many({})

class TestItemsAPI:
    def test_create_item_authenticated(self, test_token):
        token, user_id = test_token
        item_data = {
            "title": "Vélo de montagne",
            "description": "Vélo de montagne en très bon état",
            "price": 250.50,
            "category": "sports",
            "images": ["https://example.com/image1.jpg"],
            "location": "Paris"
        }

        response = client.post(
            "/api/items/",
            json=item_data,
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["title"] == item_data["title"]
        assert data["seller"] == user_id

    def test_create_item_unauthenticated(self):
        item_data = {
            "title": "Vélo de montagne",
            "description": "Vélo de montagne en très bon état",
            "price": 250.50,
            "category": "sports",
            "location": "Paris"
        }

        response = client.post("/api/items/", json=item_data)
        assert response.status_code == 401

    def test_create_item_missing_fields(self, test_token):
        token, _ = test_token
        item_data = {
            "title": "Vélo de montagne",
            # description manquante
            "price": 250.50
        }

        response = client.post(
            "/api/items/",
            json=item_data,
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 422  # FastAPI utilise 422 pour les erreurs de validation

    def test_get_all_items(self, test_token):
        token, user_id = test_token
        
        # Créer quelques objets de test
        db = get_test_db()
        db.items.insert_many([
            {
                "title": "Vélo de route",
                "description": "Vélo de route en excellent état",
                "price": 350.00,
                "category": "sports",
                "seller": user_id,
                "images": ["https://example.com/image1.jpg"],
                "location": "Paris",
                "is_active": True,
                "created_at": datetime.utcnow()
            },
            {
                "title": "Table en bois",
                "description": "Table en chêne massif",
                "price": 150.00,
                "category": "maison",
                "seller": str(ObjectId()),
                "images": ["https://example.com/image2.jpg"],
                "location": "Lyon",
                "is_active": True,
                "created_at": datetime.utcnow()
            }
        ])

        response = client.get("/api/items/")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert isinstance(data["items"], list)
        assert len(data["items"]) == 2

    def test_filter_items_by_category(self, test_token):
        token, user_id = test_token
        
        # Créer quelques objets de test
        db = get_test_db()
        db.items.insert_many([
            {
                "title": "Vélo de route",
                "description": "Vélo de route en excellent état",
                "price": 350.00,
                "category": "sports",
                "seller": user_id,
                "images": ["https://example.com/image1.jpg"],
                "location": "Paris",
                "is_active": True,
                "created_at": datetime.utcnow()
            },
            {
                "title": "Table en bois",
                "description": "Table en chêne massif",
                "price": 150.00,
                "category": "maison",
                "seller": str(ObjectId()),
                "images": ["https://example.com/image2.jpg"],
                "location": "Lyon",
                "is_active": True,
                "created_at": datetime.utcnow()
            }
        ])

        response = client.get("/api/items/?category=sports")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["category"] == "sports"

    def test_search_items(self, test_token):
        token, user_id = test_token
        
        # Créer quelques objets de test
        db = get_test_db()
        db.items.insert_many([
            {
                "title": "Vélo de route",
                "description": "Vélo de route en excellent état",
                "price": 350.00,
                "category": "sports",
                "seller": user_id,
                "images": ["https://example.com/image1.jpg"],
                "location": "Paris",
                "is_active": True,
                "created_at": datetime.utcnow()
            },
            {
                "title": "Table en bois",
                "description": "Table en chêne massif",
                "price": 150.00,
                "category": "maison",
                "seller": str(ObjectId()),
                "images": ["https://example.com/image2.jpg"],
                "location": "Lyon",
                "is_active": True,
                "created_at": datetime.utcnow()
            }
        ])

        response = client.get("/api/items/?search=vélo")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert "Vélo" in data["items"][0]["title"]

    def test_sort_items_by_price(self, test_token):
        token, user_id = test_token
        
        # Créer quelques objets de test
        db = get_test_db()
        db.items.insert_many([
            {
                "title": "Vélo de route",
                "description": "Vélo de route en excellent état",
                "price": 350.00,
                "category": "sports",
                "seller": user_id,
                "images": ["https://example.com/image1.jpg"],
                "location": "Paris",
                "is_active": True,
                "created_at": datetime.utcnow()
            },
            {
                "title": "Table en bois",
                "description": "Table en chêne massif",
                "price": 150.00,
                "category": "maison",
                "seller": str(ObjectId()),
                "images": ["https://example.com/image2.jpg"],
                "location": "Lyon",
                "is_active": True,
                "created_at": datetime.utcnow()
            }
        ])

        # Tri par prix croissant
        response = client.get("/api/items/?sort=price")
        assert response.status_code == 200
        data = response.json()
        assert data["items"][0]["price"] < data["items"][1]["price"]

        # Tri par prix décroissant
        response = client.get("/api/items/?sort=-price")
        assert response.status_code == 200
        data = response.json()
        assert data["items"][0]["price"] > data["items"][1]["price"]

    def test_pagination(self, test_token):
        token, user_id = test_token
        
        # Créer quelques objets de test
        db = get_test_db()
        db.items.insert_many([
            {
                "title": "Vélo de route",
                "description": "Vélo de route en excellent état",
                "price": 350.00,
                "category": "sports",
                "seller": user_id,
                "images": ["https://example.com/image1.jpg"],
                "location": "Paris",
                "is_active": True,
                "created_at": datetime.utcnow()
            },
            {
                "title": "Table en bois",
                "description": "Table en chêne massif",
                "price": 150.00,
                "category": "maison",
                "seller": str(ObjectId()),
                "images": ["https://example.com/image2.jpg"],
                "location": "Lyon",
                "is_active": True,
                "created_at": datetime.utcnow()
            }
        ])

        response = client.get("/api/items/?limit=1&page=1")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert "total_items" in data
        assert "total_pages" in data
        assert "current_page" in data

    def test_get_item_by_id(self, test_token):
        token, user_id = test_token
        
        # Créer un objet de test
        db = get_test_db()
        item_id = ObjectId()
        db.items.insert_one({
            "_id": item_id,
            "title": "Ordinateur portable",
            "description": "Ordinateur portable haut de gamme",
            "price": 800.00,
            "category": "électronique",
            "seller": user_id,
            "images": ["https://example.com/image3.jpg"],
            "location": "Bordeaux",
            "is_active": True,
            "created_at": datetime.utcnow()
        })

        response = client.get(f"/api/items/{str(item_id)}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(item_id)
        assert data["title"] == "Ordinateur portable"

    def test_get_nonexistent_item(self):
        nonexistent_id = str(ObjectId())
        response = client.get(f"/api/items/{nonexistent_id}")
        assert response.status_code == 404

    def test_update_item_by_owner(self, test_token):
        token, user_id = test_token
        
        # Créer un objet de test
        db = get_test_db()
        item_id = ObjectId()
        db.items.insert_one({
            "_id": item_id,
            "title": "Ordinateur portable",
            "description": "Ordinateur portable haut de gamme",
            "price": 800.00,
            "category": "électronique",
            "seller": user_id,
            "images": ["https://example.com/image3.jpg"],
            "location": "Bordeaux",
            "is_active": True,
            "created_at": datetime.utcnow()
        })

        update_data = {
            "title": "Ordinateur portable modifié",
            "price": 750.00
        }

        response = client.put(
            f"/api/items/{str(item_id)}",
            json=update_data,
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == update_data["title"]
        assert data["price"] == update_data["price"]
        assert data["description"] == "Ordinateur portable haut de gamme"  # Non modifié

    def test_update_item_unauthenticated(self, test_token):
        token, user_id = test_token
        
        # Créer un objet de test
        db = get_test_db()
        item_id = ObjectId()
        db.items.insert_one({
            "_id": item_id,
            "title": "Ordinateur portable",
            "description": "Ordinateur portable haut de gamme",
            "price": 800.00,
            "category": "électronique",
            "seller": user_id,
            "images": ["https://example.com/image3.jpg"],
            "location": "Bordeaux",
            "is_active": True,
            "created_at": datetime.utcnow()
        })

        update_data = {
            "price": 750.00
        }

        response = client.put(
            f"/api/items/{str(item_id)}",
            json=update_data
        )

        assert response.status_code == 401

    def test_update_item_by_other_user(self, test_token):
        token, user_id = test_token
        
        # Créer un token pour un autre utilisateur
        other_user_id = str(ObjectId())
        other_token = jwt.encode(
            {"sub": other_user_id, "exp": datetime.utcnow().timestamp() + 3600},
            settings.jwt_secret
        )
        
        # Créer un objet de test
        db = get_test_db()
        item_id = ObjectId()
        db.items.insert_one({
            "_id": item_id,
            "title": "Ordinateur portable",
            "description": "Ordinateur portable haut de gamme",
            "price": 800.00,
            "category": "électronique",
            "seller": user_id,  # Appartient au premier utilisateur
            "images": ["https://example.com/image3.jpg"],
            "location": "Bordeaux",
            "is_active": True,
            "created_at": datetime.utcnow()
        })

        update_data = {
            "price": 750.00
        }

        # Essayer de mettre à jour avec l'autre utilisateur
        response = client.put(
            f"/api/items/{str(item_id)}",
            json=update_data,
            headers={"Authorization": f"Bearer {other_token}"}
        )

        assert response.status_code == 403

    def test_delete_item_by_owner(self, test_token):
        token, user_id = test_token
        
        # Créer un objet de test
        db = get_test_db()
        item_id = ObjectId()
        db.items.insert_one({
            "_id": item_id,
            "title": "Ordinateur portable",
            "description": "Ordinateur portable haut de gamme",
            "price": 800.00,
            "category": "électronique",
            "seller": user_id,
            "images": ["https://example.com/image3.jpg"],
            "location": "Bordeaux",
            "is_active": True,
            "created_at": datetime.utcnow()
        })

        response = client.delete(
            f"/api/items/{str(item_id)}",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 204
        
        # Vérifier que l'objet a bien été supprimé
        db = get_test_db()
        item = db.items.find_one({"_id": item_id})
        assert item is None

    def test_delete_item_unauthenticated(self, test_token):
        token, user_id = test_token
        
        # Créer un objet de test
        db = get_test_db()
        item_id = ObjectId()
        db.items.insert_one({
            "_id": item_id,
            "title": "Ordinateur portable",
            "description": "Ordinateur portable haut de gamme",
            "price": 800.00,
            "category": "électronique",
            "seller": user_id,
            "images": ["https://example.com/image3.jpg"],
            "location": "Bordeaux",
            "is_active": True,
            "created_at": datetime.utcnow()
        })

        response = client.delete(f"/api/items/{str(item_id)}")
        assert response.status_code == 401

    def test_delete_item_by_other_user(self, test_token):
        token, user_id = test_token
        
        # Créer un token pour un autre utilisateur
        other_user_id = str(ObjectId())
        other_token = jwt.encode(
            {"sub": other_user_id, "exp": datetime.utcnow().timestamp() + 3600},
            settings.jwt_secret
        )
        
        # Créer un objet de test
        db = get_test_db()
        item_id = ObjectId()
        db.items.insert_one({
            "_id": item_id,
            "title": "Ordinateur portable",
            "description": "Ordinateur portable haut de gamme",
            "price": 800.00,
            "category": "électronique",
            "seller": user_id,  # Appartient au premier utilisateur
            "images": ["https://example.com/image3.jpg"],
            "location": "Bordeaux",
            "is_active": True,
            "created_at": datetime.utcnow()
        })

        # Essayer de supprimer avec l'autre utilisateur
        response = client.delete(
            f"/api/items/{str(item_id)}",
            headers={"Authorization": f"Bearer {other_token}"}
        )

        assert response.status_code == 403