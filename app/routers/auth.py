# app/routers/auth.py
from datetime import datetime
from app.auth.utils import verify_password
from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.security import OAuth2PasswordRequestForm
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from app.database import get_database
from app.models.user import UserCreate, UserUpdate, UserResponse, UserModel
from app.auth.utils import (
    Token, create_access_token, get_current_user, authenticate_user,
    get_user_by_email, get_password_hash, get_user_or_404
)

router = APIRouter(
    prefix="/api/auth",
    tags=["auth"],
    responses={401: {"description": "Non autorisé"}}
)

# Routes d'authentification
@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user: UserCreate,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Enregistrer un nouvel utilisateur"""
    # Vérifier si l'email est déjà utilisé
    existing_user = await get_user_by_email(user.email, db)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Un compte avec cet email existe déjà"
        )
    
    # Créer le nouvel utilisateur
    hashed_password = get_password_hash(user.password)
    new_user = {
        "email": user.email,
        "hashed_password": hashed_password,
        "full_name": user.full_name,
        "phone_number": user.phone_number,
        "is_active": True,
        "created_at": datetime.utcnow()
    }
    
    result = await db.users.insert_one(new_user)
    created_user = await db.users.find_one({"_id": result.inserted_id})
    
    return UserModel.user_response_from_mongo(created_user)

@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Se connecter et obtenir un token JWT"""
    user = await authenticate_user(form_data.username, form_data.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(
        data={"sub": str(user["_id"])}
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user_id: str = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Obtenir les informations de l'utilisateur connecté"""
    user = await get_user_or_404(current_user_id, db)
    return UserModel.user_response_from_mongo(user)

@router.put("/me", response_model=UserResponse)
async def update_user(
    user_update: UserUpdate,
    current_user_id: str = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Mettre à jour les informations de l'utilisateur connecté"""
    # Récupérer l'utilisateur actuel
    user = await get_user_or_404(current_user_id, db)
    
    # Préparer les données à mettre à jour
    update_data = {k: v for k, v in user_update.dict(exclude_unset=True).items() if v is not None}
    
    if update_data:
        update_data["updated_at"] = datetime.utcnow()
        
        # Mettre à jour l'utilisateur
        await db.users.update_one(
            {"_id": ObjectId(current_user_id)},
            {"$set": update_data}
        )
    
    # Récupérer l'utilisateur mis à jour
    updated_user = await db.users.find_one({"_id": ObjectId(current_user_id)})
    
    return UserModel.user_response_from_mongo(updated_user)

@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    current_password: str = Body(...),
    new_password: str = Body(...),
    current_user_id: str = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Changer le mot de passe de l'utilisateur connecté"""
    # Récupérer l'utilisateur actuel
    user = await get_user_or_404(current_user_id, db)
    
    # Vérifier le mot de passe actuel
    if not verify_password(current_password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mot de passe actuel incorrect"
        )
    
    # Valider le nouveau mot de passe
    try:
        UserCreate.validate_password(new_password)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    
    # Hacher et enregistrer le nouveau mot de passe
    hashed_password = get_password_hash(new_password)
    
    await db.users.update_one(
        {"_id": ObjectId(current_user_id)},
        {
            "$set": {
                "hashed_password": hashed_password,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    return None  # 204 No Content