# tests/test_auth_change_password.py
import pytest
from fastapi.testclient import TestClient
from bson import ObjectId
from datetime import datetime
import jwt
from passlib.context import CryptContext

from app.main import app
from app.config.settings import settings
from app.database import get_db

client = TestClient(app)

# Configuration pour le hachage des mots de passe
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Référence globale à la connexion de base de données
test_db = None

# Fonction pour obtenir la base de données de test
def get_test_db():
    global test_db
    if test_db is None:
        test_db = get_db()
    return test_db

# Fixture pour nettoyer la base de données après les tests
@pytest.fixture(autouse=True)
def cleanup_db():
    yield
    db = get_test_db()
    db.users.delete_many({})

# Fixture pour créer un utilisateur de test avec un mot de passe connu
@pytest.fixture
def create_test_user():
    user_id = ObjectId()
    password = "Password123!"
    hashed_password = pwd_context.hash(password)
    
    db = get_test_db()
    db.users.insert_one({
        "_id": user_id,
        "email": "test@example.com",
        "hashed_password": hashed_password,
        "full_name": "Test User",
        "phone_number": "+33612345678",
        "is_active": True,
        "created_at": datetime.utcnow()
    })
    
    token = jwt.encode(
        {"sub": str(user_id), "exp": datetime.utcnow().timestamp() + 3600},
        settings.jwt_secret
    )
    
    return {
        "id": str(user_id),
        "email": "test@example.com",
        "password": password,
        "token": token
    }

class TestChangePassword:
    
    def test_change_password_success(self, create_test_user):
        """Test pour changer le mot de passe avec succès"""
        user = create_test_user
        
        password_data = {
            "current_password": user["password"],
            "new_password": "NewPassword456!"
        }
        
        response = client.post(
            "/api/auth/change-password",
            json=password_data,
            headers={"Authorization": f"Bearer {user['token']}"}
        )
        
        assert response.status_code == 204  # No Content
        
        # Vérifier que le mot de passe a été changé en se connectant avec le nouveau mot de passe
        login_data = {
            "username": user["email"],
            "password": "NewPassword456!"
        }
        
        login_response = client.post("/api/auth/login", data=login_data)
        assert login_response.status_code == 200
        assert "access_token" in login_response.json()
    
    def test_change_password_wrong_current(self, create_test_user):
        """Test avec un mot de passe actuel incorrect"""
        user = create_test_user
        
        password_data = {
            "current_password": "WrongPassword123!",
            "new_password": "NewPassword456!"
        }
        
        response = client.post(
            "/api/auth/change-password",
            json=password_data,
            headers={"Authorization": f"Bearer {user['token']}"}
        )
        
        assert response.status_code == 400
        assert "Mot de passe actuel incorrect" in response.json()["detail"]
    
    def test_change_password_weak_new(self, create_test_user):
        """Test avec un nouveau mot de passe trop faible"""
        user = create_test_user
        
        # Mot de passe sans caractère spécial
        password_data = {
            "current_password": user["password"],
            "new_password": "NewPassword123"
        }
        
        response = client.post(
            "/api/auth/change-password",
            json=password_data,
            headers={"Authorization": f"Bearer {user['token']}"}
        )
        
        assert response.status_code == 422
        assert "caractère spécial" in response.json()["detail"].lower()
        
        # Mot de passe sans chiffre
        password_data = {
            "current_password": user["password"],
            "new_password": "NewPassword!"
        }
        
        response = client.post(
            "/api/auth/change-password",
            json=password_data,
            headers={"Authorization": f"Bearer {user['token']}"}
        )
        
        assert response.status_code == 422
        assert "chiffre" in response.json()["detail"].lower()
        
        # Mot de passe trop court
        password_data = {
            "current_password": user["password"],
            "new_password": "Np1!"
        }
        
        response = client.post(
            "/api/auth/change-password",
            json=password_data,
            headers={"Authorization": f"Bearer {user['token']}"}
        )
        
        assert response.status_code == 422
        assert "8 caractères" in response.json()["detail"].lower()
    
    def test_change_password_unauthenticated(self):
        """Test sans authentification"""
        password_data = {
            "current_password": "Password123!",
            "new_password": "NewPassword456!"
        }
        
        response = client.post(
            "/api/auth/change-password",
            json=password_data
        )
        
        assert response.status_code == 401