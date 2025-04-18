# tests/test_user_profiles.py
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
    db.ratings.delete_many({})

# Fixture pour créer un utilisateur de test
@pytest.fixture
def create_test_user():
    user_id = ObjectId()
    db = get_test_db()
    db.users.insert_one({
        "_id": user_id,
        "email": "test@example.com",
        "hashed_password": "hashed_password_here",
        "full_name": "Test User",
        "phone_number": "+33612345678",
        "is_active": True,
        "created_at": datetime.utcnow()
    })
    return str(user_id)

class TestUserProfiles:
    
    def test_get_user_profile(self, create_test_user):
        """Test pour récupérer un profil utilisateur public"""
        user_id = create_test_user
        
        response = client.get(f"/api/users/{user_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == user_id
        assert data["full_name"] == "Test User"
        assert "email" not in data  # L'email ne devrait pas être exposé publiquement
        assert "hashed_password" not in data  # Le mot de passe ne devrait jamais être exposé
    
    def test_get_nonexistent_user(self):
        """Test pour récupérer un profil utilisateur qui n'existe pas"""
        nonexistent_id = str(ObjectId())
        
        response = client.get(f"/api/users/{nonexistent_id}")
        
        assert response.status_code == 404
        assert "Utilisateur non trouvé" in response.json()["detail"]
    
    def test_get_user_ratings_empty(self, create_test_user):
        """Test pour récupérer les évaluations d'un utilisateur sans évaluations"""
        user_id = create_test_user
        
        response = client.get(f"/api/users/{user_id}/ratings")
        
        assert response.status_code == 200
        data = response.json()
        assert "ratings" in data
        assert len(data["ratings"]) == 0
        assert data["average_rating"] is None
    
    def test_get_user_ratings(self, create_test_user, test_token):
        """Test pour récupérer les évaluations d'un utilisateur avec des évaluations"""
        user_id = create_test_user
        _, rater_id = test_token
        
        # Créer quelques évaluations
        db = get_test_db()
        db.ratings.insert_many([
            {
                "rated_user": user_id,
                "rating_user": rater_id,
                "score": 5,
                "comment": "Excellent vendeur",
                "created_at": datetime.utcnow()
            },
            {
                "rated_user": user_id,
                "rating_user": str(ObjectId()),
                "score": 4,
                "comment": "Bonne transaction",
                "created_at": datetime.utcnow()
            }
        ])
        
        response = client.get(f"/api/users/{user_id}/ratings")
        
        assert response.status_code == 200
        data = response.json()
        assert "ratings" in data
        assert len(data["ratings"]) == 2
        assert data["average_rating"] == 4.5  # (5+4)/2
        
        # Vérifier que les détails de l'évaluation sont présents
        for rating in data["ratings"]:
            assert "score" in rating
            assert "comment" in rating
            assert "rating_user" in rating
            assert "created_at" in rating
    
    def test_create_user_rating(self, create_test_user, test_token):
        """Test pour créer une évaluation pour un utilisateur"""
        user_id = create_test_user
        token, rater_id = test_token
        
        rating_data = {
            "score": 4,
            "comment": "Très satisfait de la transaction"
        }
        
        response = client.post(
            f"/api/users/{user_id}/ratings",
            json=rating_data,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["score"] == rating_data["score"]
        assert data["comment"] == rating_data["comment"]
        assert data["rating_user"] == rater_id
        assert data["rated_user"] == user_id
    
    def test_cannot_rate_self(self, test_token):
        """Test pour vérifier qu'un utilisateur ne peut pas s'auto-évaluer"""
        token, user_id = test_token
        
        rating_data = {
            "score": 5,
            "comment": "Je suis génial !"
        }
        
        response = client.post(
            f"/api/users/{user_id}/ratings",
            json=rating_data,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 400
        assert "Vous ne pouvez pas vous évaluer vous-même" in response.json()["detail"]
    
    def test_invalid_rating_score(self, create_test_user, test_token):
        """Test pour vérifier la validation du score d'évaluation"""
        user_id = create_test_user
        token, _ = test_token
        
        # Score trop élevé
        rating_data = {
            "score": 6,  # Score devrait être entre 1 et 5
            "comment": "Excellent !"
        }
        
        response = client.post(
            f"/api/users/{user_id}/ratings",
            json=rating_data,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 422  # Validation error
        
        # Score trop bas
        rating_data["score"] = 0
        
        response = client.post(
            f"/api/users/{user_id}/ratings",
            json=rating_data,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 422  # Validation error