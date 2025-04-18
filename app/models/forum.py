# app/models/forum.py
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime

# Modèles pour les catégories
class ForumCategoryBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    description: str = Field(..., min_length=10, max_length=200)
    order: int = Field(..., ge=1)


class ForumCategoryInDB(ForumCategoryBase):
    id: str
    
    class Config:
        orm_mode = True


class ForumCategoryResponse(ForumCategoryInDB):
    pass


class ForumCategoriesResponse(BaseModel):
    categories: List[ForumCategoryResponse]


# Modèles pour les sujets
class ForumThreadCreate(BaseModel):
    title: str = Field(..., min_length=5, max_length=100)
    content: str = Field(..., min_length=10, max_length=5000)
    category_id: str


class ForumThreadInDB(BaseModel):
    id: str
    title: str
    author_id: str
    category_id: str
    created_at: datetime
    updated_at: datetime
    post_count: int
    is_pinned: bool = False
    is_locked: bool = False
    
    class Config:
        orm_mode = True


class ForumThreadResponse(ForumThreadInDB):
    pass


class ForumThreadListResponse(BaseModel):
    threads: List[ForumThreadResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ForumThreadLockUpdate(BaseModel):
    is_locked: bool


class ForumThreadPinUpdate(BaseModel):
    is_pinned: bool


# Modèles pour les messages
class ForumPostBase(BaseModel):
    content: str = Field(..., min_length=10, max_length=5000)


class ForumPostCreate(ForumPostBase):
    pass


class ForumPostInDB(ForumPostBase):
    id: str
    thread_id: str
    author_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        orm_mode = True


class ForumPostResponse(ForumPostInDB):
    pass


class ForumPostsResponse(BaseModel):
    posts: List[ForumPostResponse]


# Modèle combiné pour un sujet avec ses messages
class ForumThreadWithPostsResponse(ForumThreadResponse):
    posts: List[ForumPostResponse]
    first_post: Optional[ForumPostResponse] = None


# Modèles pour les conversions MongoDB -> Pydantic
class ForumModel:
    """Classe utilitaire pour convertir les documents MongoDB en modèles Pydantic"""
    
    @staticmethod
    def category_from_mongo(category):
        """Convertit un document MongoDB en modèle de catégorie Pydantic"""
        return {
            "id": str(category["_id"]),
            "name": category["name"],
            "description": category["description"],
            "order": category["order"]
        }
    
    @staticmethod
    def thread_from_mongo(thread):
        """Convertit un document MongoDB en modèle de sujet Pydantic"""
        return {
            "id": str(thread["_id"]),
            "title": thread["title"],
            "author_id": thread["author_id"],
            "category_id": thread["category_id"],
            "created_at": thread.get("created_at", datetime.utcnow()),
            "updated_at": thread.get("updated_at", datetime.utcnow()),
            "post_count": thread.get("post_count", 0),
            "is_pinned": thread.get("is_pinned", False),
            "is_locked": thread.get("is_locked", False)
        }
    
    @staticmethod
    def post_from_mongo(post):
        """Convertit un document MongoDB en modèle de message Pydantic"""
        return {
            "id": str(post["_id"]),
            "thread_id": post["thread_id"],
            "author_id": post["author_id"],
            "content": post["content"],
            "created_at": post.get("created_at", datetime.utcnow()),
            "updated_at": post.get("updated_at")
        }