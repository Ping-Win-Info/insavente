# app/models/rating.py
from typing import Optional
from pydantic import BaseModel, Field, validator
from datetime import datetime

class RatingBase(BaseModel):
    score: int = Field(..., ge=1, le=5)
    comment: Optional[str] = Field(None, min_length=3, max_length=500)
    
    @validator('score')
    def validate_score(cls, v):
        if not (1 <= v <= 5):
            raise ValueError('Le score doit être compris entre 1 et 5')
        return v


class RatingCreate(RatingBase):
    pass


class RatingInDB(RatingBase):
    id: str
    rated_user: str
    rating_user: str
    created_at: datetime
    
    class Config:
        orm_mode = True


class RatingResponse(RatingInDB):
    pass


class UserRatingsResponse(BaseModel):
    ratings: list[RatingResponse]
    average_rating: Optional[float] = None


class RatingModel:
    """Classe pour interagir avec la collection ratings dans la base de données"""
    
    @staticmethod
    def rating_from_mongo(rating):
        """Convertit un document MongoDB en modèle Pydantic"""
        return {
            "id": str(rating["_id"]),
            "score": rating["score"],
            "comment": rating.get("comment"),
            "rated_user": rating["rated_user"],
            "rating_user": rating["rating_user"],
            "created_at": rating.get("created_at", datetime.utcnow())
        }