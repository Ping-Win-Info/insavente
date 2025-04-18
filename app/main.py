# app/main.py
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from app.config.settings import settings
from app.database import setup_mongodb_indexes
from app.routers import items, auth, users, conversations, forum

# Créer l'application FastAPI
app = FastAPI(
    title=settings.app_name,
    description=settings.description,
    version=settings.version
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # A modifier en production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclure les routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(items.router)
app.include_router(conversations.router)
app.include_router(forum.router)

# Événement de démarrage pour configurer la base de données
@app.on_event("startup")
async def startup_event():
    setup_mongodb_indexes()


# Route pour vérifier que l'API fonctionne
@app.get("/", tags=["racine"])
async def root():
    return {
        "message": "Bienvenue sur l'API Social Marketplace",
        "version": settings.version,
        "status": "en ligne"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)