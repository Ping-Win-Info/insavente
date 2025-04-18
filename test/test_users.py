# tests/test_users.py
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

# Référence globale à la connexion de base de données
test_db = None

# Configuration pour le hachage des mots de passe
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

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

@pytest.fixture
def create_test_user():
    """Fixture pour créer un utilisateur de test dans la base de données"""
    db = get_test_db()
    
    # Données d'utilisateur de test
    email = "test@example.com"
    password = "Password123!"
    hashed_password = pwd_context.hash(password)
    
    user_id = ObjectId()
    
    # Créer l'utilisateur dans la base de données
    db.users.insert_one({
        "_id": user_id,
        "email": email,
        "hashed_password": hashed_password,
        "full_name": "Test User",
        "phone_number": "+33612345678",
        "is_active": True,
        "created_at": datetime.utcnow()
    })
    
    # Retourner les informations de l'utilisateur
    return {
        "id": str(user_id),
        "email": email,
        "password": password
    }

class TestUsersAuth:
    # Note: Ces tests supposent l'existence d'endpoints d'authentification
    # que vous devrez implémenter ou adapter à votre application
    
    def test_register_user(self):
        """Test d'enregistrement d'un nouvel utilisateur"""
        user_data = {
            "email": "newuser@example.com",
            "password": "SecurePassword123!",
            "full_name": "New User",
            "phone_number": "+33698765432"
        }
        
        response = client.post("/api/auth/register", json=user_data)
        
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["email"] == user_data["email"]
        assert data["full_name"] == user_data["full_name"]
        assert "hashed_password" not in data  # Vérifier que le mot de passe n'est pas exposé
    
    def test_register_duplicate_email(self):
        """Test de rejet d'un email déjà utilisé"""
        # Créer d'abord un utilisateur
        user_data = {
            "email": "duplicate@example.com",
            "password": "SecurePassword123!",
            "full_name": "First User",
            "phone_number": "+33698765432"
        }
        
        client.post("/api/auth/register", json=user_data)
        
        # Tenter de créer un second utilisateur avec le même email
        second_user_data = {
            "email": "duplicate@example.com",  # Même email
            "password": "DifferentPassword123!",
            "full_name": "Second User",
            "phone_number": "+33612345678"
        }
        
        response = client.post("/api/auth/register", json=second_user_data)
        
        assert response.status_code == 400
        assert "email existe déjà" in response.json()["detail"].lower()
    
    def test_login_user(self, create_test_user):
        """Test de connexion utilisateur et génération de token"""
        user = create_test_user
        
        login_data = {
            "username": user["email"],  # FastAPI OAuth2 utilise 'username'
            "password": user["password"]
        }
        
        response = client.post("/api/auth/login", data=login_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        
        # Vérifier que le token contient l'ID utilisateur correct
        token = data["access_token"]
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        assert payload["sub"] == user["id"]
    
    def test_login_wrong_password(self, create_test_user):
        """Test de rejet de connexion avec mot de passe incorrect"""
        user = create_test_user
        
        login_data = {
            "username": user["email"],
            "password": "WrongPassword123!"
        }
        
        response = client.post("/api/auth/login", data=login_data)
        
        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()
    
    def test_login_nonexistent_user(self):
        """Test de rejet de connexion pour un utilisateur inexistant"""
        login_data = {
            "username": "nonexistent@example.com",
            "password": "Password123!"
        }
        
        response = client.post("/api/auth/login", data=login_data)
        
        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()
    
    def test_get_current_user(self, create_test_user):
        """Test pour obtenir les informations de l'utilisateur connecté"""
        user = create_test_user
        
        # D'abord se connecter pour obtenir un token
        login_data = {
            "username": user["email"],
            "password": user["password"]
        }
        
        login_response = client.post("/api/auth/login", data=login_data)
        token = login_response.json()["access_token"]
        
        # Utiliser le token pour obtenir les infos utilisateur
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == user["id"]
        assert data["email"] == user["email"]
        assert "hashed_password" not in data
    
    def test_update_user_profile(self, create_test_user):
        """Test de mise à jour du profil utilisateur"""
        user = create_test_user
        
        # D'abord se connecter pour obtenir un token
        login_data = {
            "username": user["email"],
            "password": user["password"]
        }
        
        login_response = client.post("/api/auth/login", data=login_data)
        token = login_response.json()["access_token"]
        
        # Mettre à jour le profil
        update_data = {
            "full_name": "Updated Name",
            "phone_number": "+33612121212"
        }
        
        response = client.put(
            "/api/auth/me",
            json=update_data,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["full_name"] == update_data["full_name"]
        assert data["phone_number"] == update_data["phone_number"]
        assert data["email"] == user["email"]  # L'email ne devrait pas changer