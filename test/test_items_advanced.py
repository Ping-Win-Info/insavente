# tests/test_items_advanced.py
import pytest
from fastapi.testclient import TestClient
from bson import ObjectId
from datetime import datetime, timedelta
import jwt
import time
import json

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

# Fixture pour créer un token expiré
@pytest.fixture
def expired_token():
    test_user_id = str(ObjectId())
    token = jwt.encode(
        {"sub": test_user_id, "exp": datetime.utcnow().timestamp() - 3600},  # Expiré il y a une heure
        settings.jwt_secret
    )
    return token, test_user_id

# Fixture pour nettoyer la base de données après les tests
@pytest.fixture(autouse=True)
def cleanup_db():
    yield
    db = get_test_db()
    db.items.delete_many({})

class TestItemsAdvanced:
    # Tests de validation des données
    def test_create_item_with_negative_price(self, test_token):
        token, user_id = test_token
        item_data = {
            "title": "Produit avec prix négatif",
            "description": "Description du produit avec prix négatif pour test",
            "price": -10.00,  # Prix négatif
            "category": "électronique",
            "location": "Paris"
        }

        response = client.post(
            "/api/items/",
            json=item_data,
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 422  # Validation error
        
    def test_create_item_with_too_short_description(self, test_token):
        token, user_id = test_token
        item_data = {
            "title": "Produit",
            "description": "Trop",  # Description trop courte (moins de 10 caractères)
            "price": 50.00,
            "category": "électronique",
            "location": "Paris"
        }

        response = client.post(
            "/api/items/",
            json=item_data,
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 422

        assert response.status_code == 422

    def test_create_item_with_special_characters(self, test_token):
        token, user_id = test_token
        item_data = {
            "title": "Produit spécial !@#$%^&*()",
            "description": "Description avec caractères spéciaux éèêë et emojis 😀🔥👍",
            "price": 50.00,
            "category": "électronique",
            "location": "Paris"
        }

        response = client.post(
            "/api/items/",
            json=item_data,
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == item_data["title"]
        assert data["description"] == item_data["description"]

    # Tests de filtrage avancé
    def test_combined_filters(self, test_token):
        token, user_id = test_token
        
        # Créer des objets de test
        db = get_test_db()
        db.items.insert_many([
            {
                "title": "Téléphone Samsung",
                "description": "Téléphone Samsung Galaxy dernier modèle",
                "price": 500.00,
                "category": "électronique",
                "seller": user_id,
                "location": "Paris",
                "is_active": True,
                "created_at": datetime.utcnow()
            },
            {
                "title": "Téléphone iPhone",
                "description": "iPhone 13 Pro",
                "price": 900.00,
                "category": "électronique",
                "seller": user_id,
                "location": "Lyon",
                "is_active": True,
                "created_at": datetime.utcnow()
            },
            {
                "title": "Table en bois",
                "description": "Table en chêne pour salle à manger",
                "price": 300.00,
                "category": "maison",
                "seller": str(ObjectId()),
                "location": "Paris",
                "is_active": True,
                "created_at": datetime.utcnow()
            }
        ])

        # Tester une combinaison de filtres (catégorie + prix max + recherche)
        response = client.get("/api/items/?category=électronique&max_price=600&search=téléphone")
        assert response.status_code == 200
        data = response.json()
        
        # Vérifier que seul le téléphone Samsung est retourné
        assert len(data["items"]) == 1
        assert data["items"][0]["title"] == "Téléphone Samsung"
        assert data["items"][0]["price"] == 500.00

    def test_price_range_filter(self, test_token):
        token, user_id = test_token
        
        # Créer des objets de test
        db = get_test_db()
        db.items.insert_many([
            {
                "title": "Produit pas cher",
                "description": "Produit à bas prix",
                "price": 10.00,
                "category": "autres",
                "seller": user_id,
                "location": "Paris",
                "is_active": True,
                "created_at": datetime.utcnow()
            },
            {
                "title": "Produit prix moyen",
                "description": "Produit à prix moyen",
                "price": 50.00,
                "category": "autres",
                "seller": user_id,
                "location": "Paris",
                "is_active": True,
                "created_at": datetime.utcnow()
            },
            {
                "title": "Produit cher",
                "description": "Produit à prix élevé",
                "price": 200.00,
                "category": "autres",
                "seller": user_id,
                "location": "Paris",
                "is_active": True,
                "created_at": datetime.utcnow()
            }
        ])

        # Tester un filtre de plage de prix
        response = client.get("/api/items/?min_price=20&max_price=100")
        assert response.status_code == 200
        data = response.json()
        
        # Vérifier que seul le produit à prix moyen est retourné
        assert len(data["items"]) == 1
        assert data["items"][0]["title"] == "Produit prix moyen"

    def test_date_sorting(self, test_token):
        token, user_id = test_token
        
        # Créer des objets de test avec des dates différentes
        db = get_test_db()
        db.items.insert_many([
            {
                "title": "Produit ancien",
                "description": "Produit créé il y a 2 jours",
                "price": 50.00,
                "category": "autres",
                "seller": user_id,
                "location": "Paris",
                "is_active": True,
                "created_at": datetime.utcnow() - timedelta(days=2)
            },
            {
                "title": "Produit récent",
                "description": "Produit créé aujourd'hui",
                "price": 50.00,
                "category": "autres",
                "seller": user_id,
                "location": "Paris",
                "is_active": True,
                "created_at": datetime.utcnow()
            }
        ])

        # Trier par date (plus récent d'abord - par défaut)
        response = client.get("/api/items/")
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["items"]) == 2
        assert data["items"][0]["title"] == "Produit récent"
        assert data["items"][1]["title"] == "Produit ancien"
        
        # Trier par date (plus ancien d'abord)
        response = client.get("/api/items/?sort=created_at")
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["items"]) == 2
        assert data["items"][0]["title"] == "Produit ancien"
        assert data["items"][1]["title"] == "Produit récent"

    # Tests de gestion des erreurs
    def test_invalid_object_id(self):
        # Tester avec un ID mal formaté
        invalid_id = "not-an-object-id"
        response = client.get(f"/api/items/{invalid_id}")
        assert response.status_code == 400
        assert "ID d'objet invalide" in response.json()["detail"]

    def test_malformed_json(self, test_token):
        token, user_id = test_token
        
        # Envoyer un JSON mal formaté
        response = client.post(
            "/api/items/",
            content="{'title': 'Pas un JSON valide'",  # Utiliser content au lieu de data
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
        )
        assert response.status_code == 422  # Unprocessable Entity

    # Tests de sécurité
    def test_expired_token(self, expired_token):
        token, user_id = expired_token
        
        item_data = {
            "title": "Produit test",
            "description": "Description du produit test",
            "price": 50.00,
            "category": "électronique",
            "location": "Paris"
        }

        response = client.post(
            "/api/items/",
            json=item_data,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 401
        assert "Impossible de valider les informations d'authentification" in response.json()["detail"]

    def test_malformed_token(self):
        malformed_token = "ceci.n.est.pas.un.token.jwt.valide"
        
        item_data = {
            "title": "Produit test",
            "description": "Description du produit test",
            "price": 50.00,
            "category": "électronique",
            "location": "Paris"
        }

        response = client.post(
            "/api/items/",
            json=item_data,
            headers={"Authorization": f"Bearer {malformed_token}"}
        )
        
        assert response.status_code == 401
        assert "Impossible de valider les informations d'authentification" in response.json()["detail"]

    # Tests de fonctionnalités métier
    def test_item_deactivation(self, test_token):
        token, user_id = test_token
        
        # Créer un objet de test
        db = get_test_db()
        item_id = ObjectId()
        db.items.insert_one({
            "_id": item_id,
            "title": "Produit à désactiver",
            "description": "Description du produit à désactiver",
            "price": 50.00,
            "category": "électronique",
            "seller": user_id,
            "location": "Paris",
            "is_active": True,
            "created_at": datetime.utcnow()
        })
        
        # Désactiver l'item
        update_data = {
            "is_active": False
        }
        
        response = client.put(
            f"/api/items/{str(item_id)}",
            json=update_data,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is False
        
        # Vérifier que l'item n'apparaît plus dans les recherches (car is_active=False)
        response = client.get("/api/items/")
        assert response.status_code == 200
        data = response.json()
        
        item_ids = [item["id"] for item in data["items"]]
        assert str(item_id) not in item_ids

    def test_timestamp_updates(self, test_token):
        token, user_id = test_token
        
        # Créer un objet
        item_data = {
            "title": "Produit test",
            "description": "Description du produit test",
            "price": 50.00,
            "category": "électronique",
            "location": "Paris"
        }
        
        response = client.post(
            "/api/items/",
            json=item_data,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 201
        data = response.json()
        item_id = data["id"]
        created_at = data["created_at"]
        
        # Attendre un peu pour être sûr que updated_at sera différent
        time.sleep(1)
        
        # Mettre à jour l'objet
        update_data = {
            "title": "Produit test modifié"
        }
        
        response = client.put(
            f"/api/items/{item_id}",
            json=update_data,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Vérifier que created_at est inchangé
        assert data["created_at"] == created_at
        
        # Vérifier que updated_at a été mis à jour
        assert "updated_at" in data
        assert data["updated_at"] is not None