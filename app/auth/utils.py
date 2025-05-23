# app/auth/utils.py
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config.settings import settings
from app.database import get_database

# Configuration du hachage des mots de passe
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Schéma de token
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    user_id: Optional[str] = None


# Configuration de l'authentification OAuth2
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")


def verify_password(plain_password, hashed_password):
    """Vérifier si un mot de passe en clair correspond à un mot de passe haché"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    """Générer un hash bcrypt pour un mot de passe"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Crée un JWT token d'accès"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(seconds=settings.jwt_expiration)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.jwt_secret, 
        algorithm=settings.jwt_algorithm
    )
    
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Vérifie le token JWT et retourne l'ID de l'utilisateur"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Impossible de valider les informations d'authentification",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(
            token, 
            settings.jwt_secret, 
            algorithms=[settings.jwt_algorithm]
        )
        user_id: str = payload.get("sub")
        
        if user_id is None:
            raise credentials_exception
        
        token_data = TokenData(user_id=user_id)
    except JWTError:
        raise credentials_exception
    
    return token_data.user_id


async def get_user_by_email(email: str, db: AsyncIOMotorDatabase):
    """Récupérer un utilisateur par son email"""
    return await db.users.find_one({"email": email})


async def get_user_or_404(user_id: str, db: AsyncIOMotorDatabase):
    """Récupérer un utilisateur par son ID ou lever une exception 404"""
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


async def authenticate_user(email: str, password: str, db: AsyncIOMotorDatabase):
    """Authentifier un utilisateur avec email et mot de passe"""
    user = await get_user_by_email(email, db)
    
    if not user:
        return False
    
    if not verify_password(password, user["hashed_password"]):
        return False
    
    return user