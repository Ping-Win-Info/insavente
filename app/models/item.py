# app/models/item.py
from typing import List, Optional
from pydantic import BaseModel, Field, validator
from datetime import datetime
from enum import Enum


class CategoryEnum(str, Enum):
    ELECTRONIQUE = "électronique"
    VETEMENTS = "vêtements"
    MAISON = "maison"
    SPORTS = "sports"
    LOISIRS = "loisirs"
    AUTRES = "autres"


class ItemBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=10, max_length=2000)
    price: float = Field(..., gt=0)
    category: CategoryEnum
    location: str = Field(..., min_length=1, max_length=100)
    images: Optional[List[str]] = []
    
    @validator('price')
    def validate_price(cls, v):
        if v < 0:
            raise ValueError('Le prix ne peut pas être négatif')
        return round(v, 2)  # Arrondir à 2 décimales


class ItemCreate(ItemBase):
    pass


class ItemUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, min_length=10, max_length=2000)
    price: Optional[float] = Field(None, gt=0)
    category: Optional[CategoryEnum] = None
    location: Optional[str] = Field(None, min_length=1, max_length=100)
    images: Optional[List[str]] = None
    is_active: Optional[bool] = None
    
    @validator('price')
    def validate_price(cls, v):
        if v is not None and v < 0:
            raise ValueError('Le prix ne peut pas être négatif')
        return round(v, 2) if v is not None else None


class ItemInDB(ItemBase):
    id: str
    seller: str
    is_active: bool = True
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        orm_mode = True


class ItemResponse(ItemInDB):
    pass


class PaginatedItemsResponse(BaseModel):
    items: List[ItemResponse]
    total_items: int
    total_pages: int
    current_page: int


class ItemModel:
    """Classe pour interagir avec la collection items dans la base de données"""
    
    @staticmethod
    def item_from_mongo(item):
        """Convertit un document MongoDB en modèle Pydantic"""
        return {
            "id": str(item["_id"]),
            "title": item["title"],
            "description": item["description"],
            "price": item["price"],
            "category": item["category"],
            "location": item["location"],
            "images": item.get("images", []),
            "seller": item["seller"],
            "is_active": item.get("is_active", True),
            "created_at": item.get("created_at", datetime.utcnow()),
            "updated_at": item.get("updated_at")
        }