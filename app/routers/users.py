# app/routers/users.py
from fastapi import APIRouter, Depends, HTTPException, Path, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from datetime import datetime
from statistics import mean

from app.database import get_database
from app.auth.utils import get_current_user
from app.models.user import UserResponse, UserModel
from app.models.rating import RatingCreate, RatingResponse, UserRatingsResponse, RatingModel

router = APIRouter(
    prefix="/api/users",
    tags=["users"],
    responses={404: {"description": "Ressource non trouvée"}}
)

@router.get("/{user_id}", response_model=UserResponse, response_model_exclude={"email"})
async def get_user_profile(
    user_id: str = Path(..., title="ID de l'utilisateur à récupérer"),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Récupérer le profil public d'un utilisateur"""
    
    # Vérifier si l'ID est un ObjectId valide
    if not ObjectId.is_valid(user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID d'utilisateur invalide"
        )
    
    # Récupérer l'utilisateur
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé"
        )
    
    # Convertir en réponse
    user_data = UserModel.user_response_from_mongo(user)
    return user_data


@router.get("/{user_id}/ratings", response_model=UserRatingsResponse)
async def get_user_ratings(
    user_id: str = Path(..., title="ID de l'utilisateur dont on veut les évaluations"),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Récupérer les évaluations d'un utilisateur"""
    
    # Vérifier si l'ID est un ObjectId valide
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
    
    # Récupérer les évaluations
    cursor = db.ratings.find({"rated_user": user_id}).sort("created_at", -1)
    ratings = []
    
    async for rating in cursor:
        ratings.append(RatingModel.rating_from_mongo(rating))
    
    # Calculer la note moyenne
    average_rating = None
    if ratings:
        average_rating = round(mean([rating["score"] for rating in ratings]), 1)
    
    return {
        "ratings": ratings,
        "average_rating": average_rating
    }


@router.post("/{user_id}/ratings", response_model=RatingResponse, status_code=status.HTTP_201_CREATED)
async def create_user_rating(
    rating: RatingCreate,
    user_id: str = Path(..., title="ID de l'utilisateur à évaluer"),
    current_user_id: str = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Créer une évaluation pour un utilisateur"""
    
    # Vérifier si l'ID est un ObjectId valide
    if not ObjectId.is_valid(user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID d'utilisateur invalide"
        )
    
    # Vérifier d'abord l'auto-évaluation
    if user_id == current_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vous ne pouvez pas vous évaluer vous-même"
        )

    # Ensuite vérifier si l'utilisateur existe
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé"
        )
    
    # Empêcher l'auto-évaluation
    if user_id == current_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vous ne pouvez pas vous évaluer vous-même"
        )
    
    # Vérifier si l'utilisateur a déjà été évalué par l'utilisateur courant
    existing_rating = await db.ratings.find_one({
        "rated_user": user_id,
        "rating_user": current_user_id
    })
    
    if existing_rating:
        # Mettre à jour l'évaluation existante
        await db.ratings.update_one(
            {"_id": existing_rating["_id"]},
            {"$set": {
                "score": rating.score,
                "comment": rating.comment,
                "created_at": datetime.utcnow()
            }}
        )
        updated_rating = await db.ratings.find_one({"_id": existing_rating["_id"]})
        return RatingModel.rating_from_mongo(updated_rating)
    
    # Créer une nouvelle évaluation
    new_rating = {
        "rated_user": user_id,
        "rating_user": current_user_id,
        "score": rating.score,
        "comment": rating.comment,
        "created_at": datetime.utcnow()
    }
    
    result = await db.ratings.insert_one(new_rating)
    created_rating = await db.ratings.find_one({"_id": result.inserted_id})
    
    return RatingModel.rating_from_mongo(created_rating)