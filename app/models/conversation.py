# app/models/conversation.py
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime

class MessageBase(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000)


class MessageCreate(MessageBase):
    pass


class MessageInDB(MessageBase):
    id: str
    conversation_id: str
    sender_id: str
    created_at: datetime
    read: bool = False
    
    class Config:
        orm_mode = True


class MessageResponse(MessageInDB):
    pass


class ConversationCreate(BaseModel):
    recipient_id: str
    message: str = Field(..., min_length=1, max_length=1000)


class ConversationInDB(BaseModel):
    id: str
    participants: List[str]
    created_at: datetime
    updated_at: datetime
    last_message: str
    
    class Config:
        orm_mode = True


class ConversationResponse(ConversationInDB):
    pass


class ConversationWithMessagesResponse(ConversationResponse):
    messages: List[MessageResponse]


class ConversationsListResponse(BaseModel):
    conversations: List[ConversationResponse]


class ConversationModel:
    """Classe pour interagir avec la collection conversations dans la base de données"""
    
    @staticmethod
    def conversation_from_mongo(conversation):
        """Convertit un document MongoDB en modèle Pydantic"""
        return {
            "id": str(conversation["_id"]),
            "participants": conversation["participants"],
            "created_at": conversation.get("created_at", datetime.utcnow()),
            "updated_at": conversation.get("updated_at", datetime.utcnow()),
            "last_message": conversation.get("last_message", "")
        }


class MessageModel:
    """Classe pour interagir avec la collection messages dans la base de données"""
    
    @staticmethod
    def message_from_mongo(message):
        """Convertit un document MongoDB en modèle Pydantic"""
        return {
            "id": str(message["_id"]),
            "conversation_id": message["conversation_id"],
            "sender_id": message["sender_id"],
            "content": message["content"],
            "created_at": message.get("created_at", datetime.utcnow()),
            "read": message.get("read", False)
        }