# app/config/settings.py
from pydantic import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "Social Marketplace API"
    description: str = "API pour une plateforme sociale de vente d'objets"
    version: str = "0.1.0"
    
    # Configuration MongoDB
    mongodb_url: str = "mongodb://localhost:27017"
    database_name: str = "social_marketplace"
    
    # Configuration JWT
    jwt_secret: str = "votre_secret_jwt_a_changer_en_production"
    jwt_algorithm: str = "HS256"
    jwt_expiration: int = 3600  # Durée de validité du token en secondes (1h)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()