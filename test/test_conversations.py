# tests/test_conversations.py
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
    db.conversations.delete_many({})
    db.messages.delete_many({})

# Fixture pour créer deux utilisateurs pour les conversations
@pytest.fixture
def create_two_users():
    user1_id = ObjectId()
    user2_id = ObjectId()
    db = get_test_db()
    
    db.users.insert_many([
        {
            "_id": user1_id,
            "email": "user1@example.com",
            "hashed_password": "hashed_password_here",
            "full_name": "User One",
            "phone_number": "+33612345678",
            "is_active": True,
            "created_at": datetime.utcnow()
        },
        {
            "_id": user2_id,
            "email": "user2@example.com",
            "hashed_password": "hashed_password_here",
            "full_name": "User Two",
            "phone_number": "+33687654321",
            "is_active": True,
            "created_at": datetime.utcnow()
        }
    ])
    
    return str(user1_id), str(user2_id)

class TestConversations:
    
    def test_start_new_conversation(self, test_token, create_two_users):
        """Test pour démarrer une nouvelle conversation"""
        token, user1_id = test_token
        _, user2_id = create_two_users
        
        # Remplacer l'ID de l'utilisateur 1 par l'ID du token pour assurer la cohérence
        db = get_test_db()
        db.users.update_one({"_id": ObjectId(user1_id)}, {"$set": {"_id": ObjectId(user1_id)}})
        
        conversation_data = {
            "recipient_id": user2_id,
            "message": "Bonjour, je suis intéressé par votre annonce"
        }
        
        response = client.post(
            "/api/conversations",
            json=conversation_data,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert "participants" in data
        assert user1_id in data["participants"]
        assert user2_id in data["participants"]
        assert "messages" in data
        assert len(data["messages"]) == 1
        assert data["messages"][0]["content"] == conversation_data["message"]
        assert data["messages"][0]["sender_id"] == user1_id
    
    def test_get_conversations_list(self, test_token, create_two_users):
        """Test pour récupérer la liste des conversations d'un utilisateur"""
        token, user1_id = test_token
        _, user2_id = create_two_users
        
        # Créer quelques conversations
        db = get_test_db()
        conversation1_id = ObjectId()
        conversation2_id = ObjectId()
        
        db.conversations.insert_many([
            {
                "_id": conversation1_id,
                "participants": [user1_id, user2_id],
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "last_message": "Bonjour"
            },
            {
                "_id": conversation2_id,
                "participants": [user1_id, str(ObjectId())],  # Autre utilisateur
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "last_message": "Salut"
            }
        ])
        
        response = client.get(
            "/api/conversations",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "conversations" in data
        assert len(data["conversations"]) == 2
        
        # Vérifier que les détails des conversations sont présents
        for conversation in data["conversations"]:
            assert "id" in conversation
            assert "participants" in conversation
            assert "last_message" in conversation
            assert "updated_at" in conversation
            assert user1_id in conversation["participants"]
    
    def test_get_conversation_messages(self, test_token, create_two_users):
        """Test pour récupérer les messages d'une conversation spécifique"""
        token, user1_id = test_token
        _, user2_id = create_two_users
        
        # Créer une conversation avec des messages
        db = get_test_db()
        conversation_id = ObjectId()
        
        db.conversations.insert_one({
            "_id": conversation_id,
            "participants": [user1_id, user2_id],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "last_message": "Bonjour"
        })
        
        db.messages.insert_many([
            {
                "conversation_id": str(conversation_id),
                "sender_id": user1_id,
                "content": "Bonjour, je suis intéressé par votre annonce",
                "created_at": datetime.utcnow(),
                "read": False
            },
            {
                "conversation_id": str(conversation_id),
                "sender_id": user2_id,
                "content": "Bonjour, c'est toujours disponible",
                "created_at": datetime.utcnow(),
                "read": False
            }
        ])
        
        response = client.get(
            f"/api/conversations/{str(conversation_id)}",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "messages" in data
        assert len(data["messages"]) == 2
        
        # Vérifier que les détails des messages sont présents
        for message in data["messages"]:
            assert "sender_id" in message
            assert "content" in message
            assert "created_at" in message
            assert "read" in message
    
    def test_send_message_to_conversation(self, test_token, create_two_users):
        """Test pour envoyer un message dans une conversation existante"""
        token, user1_id = test_token
        _, user2_id = create_two_users
        
        # Créer une conversation
        db = get_test_db()
        conversation_id = ObjectId()
        
        db.conversations.insert_one({
            "_id": conversation_id,
            "participants": [user1_id, user2_id],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "last_message": "Bonjour"
        })
        
        message_data = {
            "content": "Est-ce que je peux venir le voir demain ?"
        }
        
        response = client.post(
            f"/api/conversations/{str(conversation_id)}/messages",
            json=message_data,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["content"] == message_data["content"]
        assert data["sender_id"] == user1_id
        assert data["conversation_id"] == str(conversation_id)
        assert data["read"] is False
        
        # Vérifier que la conversation a été mise à jour
        conversation = db.conversations.find_one({"_id": conversation_id})
        assert conversation["last_message"] == message_data["content"]
        assert conversation["updated_at"] > conversation["created_at"]
    
    def test_cannot_access_others_conversation(self, test_token):
        """Test pour vérifier qu'un utilisateur ne peut pas accéder à une conversation dont il n'est pas participant"""
        token, user1_id = test_token
        
        # Créer une conversation entre deux autres utilisateurs
        db = get_test_db()
        conversation_id = ObjectId()
        
        db.conversations.insert_one({
            "_id": conversation_id,
            "participants": [str(ObjectId()), str(ObjectId())],  # Deux utilisateurs différents
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "last_message": "Bonjour"
        })
        
        response = client.get(
            f"/api/conversations/{str(conversation_id)}",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 403
        assert "Vous n'êtes pas autorisé à accéder à cette conversation" in response.json()["detail"]
    
    def test_mark_messages_as_read(self, test_token, create_two_users):
        """Test pour marquer tous les messages d'une conversation comme lus"""
        token, user1_id = test_token
        _, user2_id = create_two_users
        
        # Créer une conversation avec des messages non lus
        db = get_test_db()
        conversation_id = ObjectId()
        
        db.conversations.insert_one({
            "_id": conversation_id,
            "participants": [user1_id, user2_id],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "last_message": "Bonjour"
        })
        
        db.messages.insert_many([
            {
                "conversation_id": str(conversation_id),
                "sender_id": user2_id,  # Messages de l'autre utilisateur
                "content": "Bonjour, c'est toujours disponible",
                "created_at": datetime.utcnow(),
                "read": False
            },
            {
                "conversation_id": str(conversation_id),
                "sender_id": user2_id,
                "content": "Je peux vous proposer un bon prix",
                "created_at": datetime.utcnow(),
                "read": False
            }
        ])
        
        response = client.put(
            f"/api/conversations/{str(conversation_id)}/read",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        
        # Vérifier que tous les messages ont été marqués comme lus
        messages = list(db.messages.find({"conversation_id": str(conversation_id)}))
        for message in messages:
            assert message["read"] is True