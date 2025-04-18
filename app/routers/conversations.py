# app/routers/conversations.py
from fastapi import APIRouter, Depends, HTTPException, Path, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from datetime import datetime

from app.database import get_database
from app.auth.utils import get_current_user
from app.models.conversation import (
    ConversationCreate, ConversationResponse, ConversationWithMessagesResponse,
    ConversationsListResponse, MessageCreate, MessageResponse,
    ConversationModel, MessageModel
)

router = APIRouter(
    prefix="/api/conversations",
    tags=["conversations"],
    responses={404: {"description": "Ressource non trouvée"}}
)


async def check_user_exists(user_id: str, db: AsyncIOMotorDatabase):
    """Vérifier si un utilisateur existe"""
    if not ObjectId.is_valid(user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID d'utilisateur invalide"
        )
    
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé"
        )
    
    return user


async def check_conversation_access(conversation_id: str, user_id: str, db: AsyncIOMotorDatabase):
    """Vérifier si l'utilisateur a accès à la conversation"""
    if not ObjectId.is_valid(conversation_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID de conversation invalide"
        )
    
    conversation = await db.conversations.find_one({"_id": ObjectId(conversation_id)})
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation non trouvée"
        )
    
    if user_id not in conversation["participants"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'êtes pas autorisé à accéder à cette conversation"
        )
    
    return conversation


@router.post("/", response_model=ConversationWithMessagesResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    conversation_data: ConversationCreate,
    current_user_id: str = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Démarrer une nouvelle conversation avec un message initial"""
    
    # Vérifier que le destinataire existe
    await check_user_exists(conversation_data.recipient_id, db)
    
    # Empêcher de démarrer une conversation avec soi-même
    if conversation_data.recipient_id == current_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vous ne pouvez pas démarrer une conversation avec vous-même"
        )
    
    # Vérifier si une conversation existe déjà entre ces utilisateurs
    existing_conversation = await db.conversations.find_one({
        "participants": {"$all": [current_user_id, conversation_data.recipient_id]},
        "participants": {"$size": 2}  # Assurer qu'il n'y a que ces deux participants
    })
    
    if existing_conversation:
        # Ajouter un message à la conversation existante
        message = {
            "conversation_id": str(existing_conversation["_id"]),
            "sender_id": current_user_id,
            "content": conversation_data.message,
            "created_at": datetime.utcnow(),
            "read": False
        }
        
        await db.messages.insert_one(message)
        
        # Mettre à jour la conversation
        await db.conversations.update_one(
            {"_id": existing_conversation["_id"]},
            {
                "$set": {
                    "last_message": conversation_data.message,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        # Récupérer la conversation mise à jour avec tous les messages
        return await get_conversation_with_messages(
            str(existing_conversation["_id"]),
            current_user_id,
            db
        )
    
    # Créer une nouvelle conversation
    now = datetime.utcnow()
    new_conversation = {
        "participants": [current_user_id, conversation_data.recipient_id],
        "created_at": now,
        "updated_at": now,
        "last_message": conversation_data.message
    }
    
    result = await db.conversations.insert_one(new_conversation)
    conversation_id = str(result.inserted_id)
    
    # Ajouter le premier message
    message = {
        "conversation_id": conversation_id,
        "sender_id": current_user_id,
        "content": conversation_data.message,
        "created_at": now,
        "read": False
    }
    
    await db.messages.insert_one(message)
    
    # Récupérer la conversation avec le message
    return await get_conversation_with_messages(conversation_id, current_user_id, db)


@router.get("/", response_model=ConversationsListResponse)
async def get_conversations(
    current_user_id: str = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Récupérer la liste des conversations de l'utilisateur"""
    
    # Trouver toutes les conversations où l'utilisateur est participant
    cursor = db.conversations.find(
        {"participants": current_user_id}
    ).sort("updated_at", -1)  # Trier par date de mise à jour décroissante
    
    conversations = []
    async for conversation in cursor:
        conversations.append(ConversationModel.conversation_from_mongo(conversation))
    
    return {"conversations": conversations}


@router.get("/{conversation_id}", response_model=ConversationWithMessagesResponse)
async def get_conversation(
    conversation_id: str = Path(..., title="ID de la conversation à récupérer"),
    current_user_id: str = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Récupérer une conversation spécifique avec ses messages"""
    return await get_conversation_with_messages(conversation_id, current_user_id, db)


async def get_conversation_with_messages(conversation_id: str, user_id: str, db: AsyncIOMotorDatabase):
    """Fonction utilitaire pour récupérer une conversation avec ses messages"""
    
    # Vérifier l'accès à la conversation
    conversation = await check_conversation_access(conversation_id, user_id, db)
    
    # Récupérer les messages de la conversation
    cursor = db.messages.find(
        {"conversation_id": conversation_id}
    ).sort("created_at", 1)  # Trier par date croissante
    
    messages = []
    async for message in cursor:
        messages.append(MessageModel.message_from_mongo(message))
    
    # Marquer automatiquement les messages comme lus
    await db.messages.update_many(
        {
            "conversation_id": conversation_id,
            "sender_id": {"$ne": user_id},  # Messages des autres utilisateurs
            "read": False
        },
        {"$set": {"read": True}}
    )
    
    # Retourner la conversation avec ses messages
    conversation_data = ConversationModel.conversation_from_mongo(conversation)
    conversation_data["messages"] = messages
    
    return conversation_data


@router.post("/{conversation_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def create_message(
    message_data: MessageCreate,
    conversation_id: str = Path(..., title="ID de la conversation"),
    current_user_id: str = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Envoyer un message dans une conversation existante"""
    
    # Vérifier l'accès à la conversation
    conversation = await check_conversation_access(conversation_id, current_user_id, db)
    
    # Créer le message
    new_message = {
        "conversation_id": conversation_id,
        "sender_id": current_user_id,
        "content": message_data.content,
        "created_at": datetime.utcnow(),
        "read": False
    }
    
    result = await db.messages.insert_one(new_message)
    created_message = await db.messages.find_one({"_id": result.inserted_id})
    
    # Mettre à jour la conversation
    await db.conversations.update_one(
        {"_id": ObjectId(conversation_id)},
        {
            "$set": {
                "last_message": message_data.content,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    return MessageModel.message_from_mongo(created_message)


@router.put("/{conversation_id}/read", status_code=status.HTTP_200_OK)
async def mark_messages_as_read(
    conversation_id: str = Path(..., title="ID de la conversation"),
    current_user_id: str = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Marquer tous les messages d'une conversation comme lus"""
    
    # Vérifier l'accès à la conversation
    await check_conversation_access(conversation_id, current_user_id, db)
    
    # Marquer tous les messages des autres utilisateurs comme lus
    result = await db.messages.update_many(
        {
            "conversation_id": conversation_id,
            "sender_id": {"$ne": current_user_id},
            "read": False
        },
        {"$set": {"read": True}}
    )
    
    return {"marked_as_read": result.modified_count}