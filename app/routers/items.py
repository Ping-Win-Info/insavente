# app/routers/items.py
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from bson import ObjectId
from datetime import datetime
from pymongo import ASCENDING, DESCENDING
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.item import (
    ItemCreate, 
    ItemUpdate, 
    ItemResponse, 
    PaginatedItemsResponse,
    ItemModel
)
from app.database import get_database
from app.auth.utils import get_current_user

router = APIRouter(
    prefix="/api/items",
    tags=["items"],
    responses={404: {"description": "Ressource non trouvée"}}
)


@router.post("/", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
async def create_item(
    item: ItemCreate,
    current_user_id: str = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Créer un nouvel objet à vendre"""
    
    # Préparer l'objet à insérer
    new_item = {
        "title": item.title,
        "description": item.description,
        "price": item.price,
        "category": item.category,
        "location": item.location,
        "images": item.images,
        "seller": current_user_id,
        "is_active": True,
        "created_at": datetime.utcnow()
    }
    
    # Insérer l'objet dans la base de données
    result = await db.items.insert_one(new_item)
    
    # Récupérer l'objet créé
    created_item = await db.items.find_one({"_id": result.inserted_id})
    
    return ItemModel.item_from_mongo(created_item)


@router.get("/", response_model=PaginatedItemsResponse)
async def get_items(
    search: Optional[str] = None,
    category: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    sort: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Récupérer la liste des objets avec filtrage, tri et pagination"""
    
    # Construire le filtre de recherche
    filter_query = {"is_active": True}
    
    if category:
        filter_query["category"] = category
    
    if min_price is not None or max_price is not None:
        filter_query["price"] = {}
        if min_price is not None:
            filter_query["price"]["$gte"] = min_price
        if max_price is not None:
            filter_query["price"]["$lte"] = max_price
    
    # Recherche textuelle
    if search:
        filter_query["$text"] = {"$search": search}
    
    # Calculer le skip pour la pagination
    skip = (page - 1) * limit
    
    # Déterminer l'ordre de tri
    sort_dict = {"created_at": -1}  # Par défaut, les plus récents d'abord
    
    if sort:
        if sort.startswith("-"):
            sort_field = sort[1:]
            sort_direction = -1
        else:
            sort_field = sort
            sort_direction = 1
        
        sort_dict = {sort_field: sort_direction}
    
    # Récupérer les objets paginés
    cursor = db.items.find(filter_query).sort(list(sort_dict.items())).skip(skip).limit(limit)
    items = []
    
    async for item in cursor:
        items.append(ItemModel.item_from_mongo(item))
    
    # Compter le nombre total d'objets pour la pagination
    total_items = await db.items.count_documents(filter_query)
    total_pages = (total_items + limit - 1) // limit  # Arrondir au supérieur
    
    return {
        "items": items,
        "total_items": total_items,
        "total_pages": total_pages,
        "current_page": page
    }


@router.get("/{item_id}", response_model=ItemResponse)
async def get_item_by_id(
    item_id: str = Path(..., title="ID de l'objet à récupérer"),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Récupérer un objet spécifique par son ID"""
    
    # Vérifier si l'ID est un ObjectId valide
    if not ObjectId.is_valid(item_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID d'objet invalide"
        )
    
    # Récupérer l'objet
    item = await db.items.find_one({"_id": ObjectId(item_id)})
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Objet non trouvé"
        )
    
    return ItemModel.item_from_mongo(item)


@router.put("/{item_id}", response_model=ItemResponse)
async def update_item(
    item_update: ItemUpdate,
    item_id: str = Path(..., title="ID de l'objet à mettre à jour"),
    current_user_id: str = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Mettre à jour un objet existant"""
    
    # Vérifier si l'ID est un ObjectId valide
    if not ObjectId.is_valid(item_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID d'objet invalide"
        )
    
    # Récupérer l'objet existant
    item = await db.items.find_one({"_id": ObjectId(item_id)})
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Objet non trouvé"
        )
    
    # Vérifier si l'utilisateur est le vendeur
    if item["seller"] != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'êtes pas autorisé à modifier cet objet"
        )
    
    # Préparer les données à mettre à jour
    update_data = {k: v for k, v in item_update.dict(exclude_unset=True).items()}
    
    if update_data:
        update_data["updated_at"] = datetime.utcnow()
        
        # Mettre à jour l'objet
        await db.items.update_one(
            {"_id": ObjectId(item_id)},
            {"$set": update_data}
        )
    
    # Récupérer l'objet mis à jour
    updated_item = await db.items.find_one({"_id": ObjectId(item_id)})
    
    return ItemModel.item_from_mongo(updated_item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    item_id: str = Path(..., title="ID de l'objet à supprimer"),
    current_user_id: str = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Supprimer un objet"""
    
    # Vérifier si l'ID est un ObjectId valide
    if not ObjectId.is_valid(item_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID d'objet invalide"
        )
    
    # Récupérer l'objet existant
    item = await db.items.find_one({"_id": ObjectId(item_id)})
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Objet non trouvé"
        )
    
    # Vérifier si l'utilisateur est le vendeur
    if item["seller"] != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'êtes pas autorisé à supprimer cet objet"
        )
    
    # Supprimer l'objet
    await db.items.delete_one({"_id": ObjectId(item_id)})
    
    return None