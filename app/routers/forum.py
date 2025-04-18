# app/routers/forum.py
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from datetime import datetime
from typing import Optional

from app.database import get_database
from app.auth.utils import get_current_user
from app.models.forum import (
    ForumCategoriesResponse, ForumThreadCreate, ForumThreadResponse,
    ForumThreadWithPostsResponse, ForumThreadListResponse, 
    ForumPostCreate, ForumPostResponse, ForumThreadLockUpdate,
    ForumThreadPinUpdate, ForumModel
)

router = APIRouter(
    prefix="/api/forum",
    tags=["forum"],
    responses={404: {"description": "Ressource non trouvée"}}
)


# Helper function pour vérifier si un utilisateur est admin
async def is_admin(user_id: str, db: AsyncIOMotorDatabase) -> bool:
    """Vérifier si un utilisateur est administrateur"""
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    return user is not None and user.get("is_admin", False)


@router.get("/categories", response_model=ForumCategoriesResponse)
async def get_forum_categories(
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Récupérer toutes les catégories du forum"""
    
    cursor = db.forum_categories.find().sort("order", 1)
    categories = []
    
    async for category in cursor:
        categories.append(ForumModel.category_from_mongo(category))
    
    return {"categories": categories}


@router.post("/threads", response_model=ForumThreadWithPostsResponse, status_code=status.HTTP_201_CREATED)
async def create_thread(
    thread_data: ForumThreadCreate,
    current_user_id: str = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Créer un nouveau sujet dans le forum avec son premier message"""
    
    # Vérifier si la catégorie existe
    if not ObjectId.is_valid(thread_data.category_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID de catégorie invalide"
        )
    
    category = await db.forum_categories.find_one({"_id": ObjectId(thread_data.category_id)})
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Catégorie non trouvée"
        )
    
    # Créer le sujet
    now = datetime.utcnow()
    new_thread = {
        "title": thread_data.title,
        "author_id": current_user_id,
        "category_id": thread_data.category_id,
        "created_at": now,
        "updated_at": now,
        "post_count": 1,
        "is_pinned": False,
        "is_locked": False
    }
    
    thread_result = await db.forum_threads.insert_one(new_thread)
    thread_id = str(thread_result.inserted_id)
    
    # Créer le premier message du sujet
    first_post = {
        "thread_id": thread_id,
        "author_id": current_user_id,
        "content": thread_data.content,
        "created_at": now,
        "updated_at": None
    }
    
    post_result = await db.forum_posts.insert_one(first_post)
    
    # Récupérer le sujet créé avec son premier message
    thread = await db.forum_threads.find_one({"_id": ObjectId(thread_id)})
    post = await db.forum_posts.find_one({"_id": post_result.inserted_id})
    
    thread_response = ForumModel.thread_from_mongo(thread)
    first_post_response = ForumModel.post_from_mongo(post)
    
    return {
        **thread_response,
        "posts": [first_post_response],
        "first_post": first_post_response
    }


@router.get("/threads", response_model=ForumThreadListResponse)
async def get_threads(
    category_id: Optional[str] = Query(None, title="ID de la catégorie pour filtrer les sujets"),
    search: Optional[str] = Query(None, title="Terme de recherche dans les titres"),
    page: int = Query(1, ge=1, title="Numéro de page"),
    page_size: int = Query(20, ge=5, le=50, title="Nombre d'éléments par page"),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Récupérer la liste des sujets du forum avec filtrage et pagination"""
    
    # Construire le filtre
    filter_query = {}
    
    if category_id:
        if not ObjectId.is_valid(category_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ID de catégorie invalide"
            )
        filter_query["category_id"] = category_id
    
    if search:
        filter_query["$text"] = {"$search": search}
    
    # Compter le nombre total de sujets
    total = await db.forum_threads.count_documents(filter_query)
    
    # Récupérer les sujets avec pagination
    skip = (page - 1) * page_size
    
    # D'abord les sujets épinglés, puis les autres par date de mise à jour décroissante
    cursor = db.forum_threads.find(filter_query).sort([
        ("is_pinned", -1),  # -1 signifie ordre décroissant (les épinglés d'abord)
        ("updated_at", -1)   # Les plus récents d'abord
    ]).skip(skip).limit(page_size)
    
    threads = []
    async for thread in cursor:
        threads.append(ForumModel.thread_from_mongo(thread))
    
    # Calculer le nombre total de pages
    total_pages = (total + page_size - 1) // page_size  # Arrondi supérieur
    
    return {
        "threads": threads,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }


@router.get("/threads/{thread_id}", response_model=ForumThreadWithPostsResponse)
async def get_thread_with_posts(
    thread_id: str = Path(..., title="ID du sujet à récupérer"),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Récupérer un sujet spécifique avec tous ses messages"""
    
    # Vérifier si l'ID est valide
    if not ObjectId.is_valid(thread_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID de sujet invalide"
        )
    
    # Récupérer le sujet
    thread = await db.forum_threads.find_one({"_id": ObjectId(thread_id)})
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sujet non trouvé"
        )
    
    # Récupérer tous les messages du sujet
    cursor = db.forum_posts.find({"thread_id": thread_id}).sort("created_at", 1)
    posts = []
    first_post = None
    
    async for post in cursor:
        post_data = ForumModel.post_from_mongo(post)
        posts.append(post_data)
        
        # Stocker le premier message
        if first_post is None:
            first_post = post_data
    
    thread_data = ForumModel.thread_from_mongo(thread)
    
    return {
        **thread_data,
        "posts": posts,
        "first_post": first_post
    }


@router.post("/threads/{thread_id}/posts", response_model=ForumPostResponse, status_code=status.HTTP_201_CREATED)
async def create_post(
    post_data: ForumPostCreate,
    thread_id: str = Path(..., title="ID du sujet"),
    current_user_id: str = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Ajouter un message à un sujet existant"""
    
    # Vérifier si l'ID est valide
    if not ObjectId.is_valid(thread_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID de sujet invalide"
        )
    
    # Récupérer le sujet
    thread = await db.forum_threads.find_one({"_id": ObjectId(thread_id)})
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sujet non trouvé"
        )
    
    # Vérifier si le sujet est verrouillé
    if thread.get("is_locked", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ce sujet est verrouillé et n'accepte plus de nouveaux messages"
        )
    
    # Créer le message
    now = datetime.utcnow()
    new_post = {
        "thread_id": thread_id,
        "author_id": current_user_id,
        "content": post_data.content,
        "created_at": now,
        "updated_at": None
    }
    
    result = await db.forum_posts.insert_one(new_post)
    created_post = await db.forum_posts.find_one({"_id": result.inserted_id})
    
    # Mettre à jour le compteur de messages et la date de mise à jour du sujet
    await db.forum_threads.update_one(
        {"_id": ObjectId(thread_id)},
        {
            "$inc": {"post_count": 1},
            "$set": {"updated_at": now}
        }
    )
    
    return ForumModel.post_from_mongo(created_post)


@router.put("/threads/{thread_id}/lock", response_model=ForumThreadResponse)
async def lock_thread(
    lock_data: ForumThreadLockUpdate,
    thread_id: str = Path(..., title="ID du sujet à verrouiller/déverrouiller"),
    current_user_id: str = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Verrouiller ou déverrouiller un sujet (action réservée aux administrateurs)"""
    
    # Vérifier si l'utilisateur est admin
    if not await is_admin(current_user_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Droits d'administrateur requis pour cette action"
        )
    
    # Vérifier si l'ID est valide
    if not ObjectId.is_valid(thread_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID de sujet invalide"
        )
    
    # Récupérer le sujet
    thread = await db.forum_threads.find_one({"_id": ObjectId(thread_id)})
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sujet non trouvé"
        )
    
    # Mettre à jour le statut de verrouillage
    await db.forum_threads.update_one(
        {"_id": ObjectId(thread_id)},
        {"$set": {"is_locked": lock_data.is_locked}}
    )
    
    # Récupérer le sujet mis à jour
    updated_thread = await db.forum_threads.find_one({"_id": ObjectId(thread_id)})
    
    return ForumModel.thread_from_mongo(updated_thread)


@router.put("/threads/{thread_id}/pin", response_model=ForumThreadResponse)
async def pin_thread(
    pin_data: ForumThreadPinUpdate,
    thread_id: str = Path(..., title="ID du sujet à épingler/désépingler"),
    current_user_id: str = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Épingler ou désépingler un sujet (action réservée aux administrateurs)"""
    
    # Vérifier si l'utilisateur est admin
    if not await is_admin(current_user_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Droits d'administrateur requis pour cette action"
        )
    
    # Vérifier si l'ID est valide
    if not ObjectId.is_valid(thread_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID de sujet invalide"
        )
    
    # Récupérer le sujet
    thread = await db.forum_threads.find_one({"_id": ObjectId(thread_id)})
    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sujet non trouvé"
        )
    
    # Mettre à jour le statut d'épinglage
    await db.forum_threads.update_one(
        {"_id": ObjectId(thread_id)},
        {"$set": {"is_pinned": pin_data.is_pinned}}
    )
    
    # Récupérer le sujet mis à jour
    updated_thread = await db.forum_threads.find_one({"_id": ObjectId(thread_id)})
    
    return ForumModel.thread_from_mongo(updated_thread)