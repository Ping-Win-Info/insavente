# app/models/user.py
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, validator
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=100)
    phone_number: str = Field(..., min_length=8, max_length=15)
    
    @validator('phone_number')
    def validate_phone_number(cls, v):
        if not (v.startswith('+') and v[1:].isdigit()):
            raise ValueError('Le numéro de téléphone doit commencer par + suivi uniquement de chiffres')
        return v

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    
    @validator('password')
    def validate_password(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError('Le mot de passe doit contenir au moins une majuscule')
        if not any(c.islower() for c in v):
            raise ValueError('Le mot de passe doit contenir au moins une minuscule')
        if not any(c.isdigit() for c in v):
            raise ValueError('Le mot de passe doit contenir au moins un chiffre')
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?/" for c in v):
            raise ValueError('Le mot de passe doit contenir au moins un caractère spécial')
        return v
    
    # Méthode statique pour valider un mot de passe indépendamment d'une instance
    @staticmethod
    def validate_password(password):
        if len(password) < 8:
            raise ValueError('Le mot de passe doit contenir au moins 8 caractères')
        if not any(c.isupper() for c in password):
            raise ValueError('Le mot de passe doit contenir au moins une majuscule')
        if not any(c.islower() for c in password):
            raise ValueError('Le mot de passe doit contenir au moins une minuscule')
        if not any(c.isdigit() for c in password):
            raise ValueError('Le mot de passe doit contenir au moins un chiffre')
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?/" for c in password):
            raise ValueError('Le mot de passe doit contenir au moins un caractère spécial')
        return password

class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    phone_number: Optional[str] = Field(None, min_length=8, max_length=15)
    
    @validator('phone_number')
    def validate_phone_number(cls, v):
        if v is not None and not (v.startswith('+') and v[1:].isdigit()):
            raise ValueError('Le numéro de téléphone doit commencer par + suivi uniquement de chiffres')
        return v

class UserResponse(UserBase):
    id: str
    email: Optional[EmailStr] = None  # Rendre l'email optionnel
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        orm_mode = True

class UserInDB(UserBase):
    id: str
    hashed_password: str
    is_active: bool = True
    created_at: datetime
    updated_at: Optional[datetime] = None

class UserModel:
    """Classe pour interagir avec la collection users dans la base de données"""
    
    @staticmethod
    def user_from_mongo(user):
        """Convertit un document MongoDB en modèle Pydantic"""
        return {
            "id": str(user["_id"]),
            "email": user["email"],
            "full_name": user["full_name"],
            "phone_number": user["phone_number"],
            "hashed_password": user["hashed_password"],
            "is_active": user.get("is_active", True),
            "created_at": user.get("created_at", datetime.utcnow()),
            "updated_at": user.get("updated_at")
        }
    
    @staticmethod
    def user_response_from_mongo(user):
        """Convertit un document MongoDB en réponse utilisateur (sans mot de passe)"""
        user_dict = UserModel.user_from_mongo(user)
        del user_dict["hashed_password"]
        return user_dict