# tests/test_performance.py
import pytest
import time
from fastapi.testclient import TestClient
from bson import ObjectId
from datetime import datetime, timedelta
import random
import string
import jwt

from app.main import app
from app.config.settings import settings
from app.database import get_db

client = TestClient(app)

# Référence globale à la connexion de base de données
test_db = None

# Fonction pour obtenir la base de données de test
def get_test_db():
    global test_db
    if test_db is None:
        test_db = get_db()
    return test_db

# Fixture pour créer un token de test
@pytest.fixture
def test_token():
    test_user_id = str(ObjectId())
    token = jwt.encode(
        {"sub": test_user_id, "exp": datetime.utcnow().timestamp() + 3600},
        settings.jwt_secret
    )
    return token, test_user_id

# Fixture pour créer beaucoup d'items de test
@pytest.fixture
def create_many_items():
    """Créer 100 items pour les tests de performance"""
    db = get_test_db()
    seller_id = str(ObjectId())
    
    # Générer des données aléatoires pour 100 items
    items = []
    categories = ["électronique", "vêtements", "maison", "sports", "loisirs", "autres"]
    
    for i in range(100):
        # Générer un titre et une description aléatoire
        title = f"Produit {i+1} - {''.join(random.choices(string.ascii_letters, k=10))}"
        desc = ''.join(random.choices(string.ascii_letters + ' ', k=100))
        
        items.append({
            "title": title,
            "description": desc,
            "price": round(random.uniform(10.0, 1000.0), 2),
            "category": random.choice(categories),
            "seller": seller_id,
            "location": random.choice(["Paris", "Lyon", "Marseille", "Toulouse", "Bordeaux"]),
            "is_active": True,
            "created_at": datetime.utcnow() - timedelta(days=random.randint(0, 30))
        })
    
    db.items.insert_many(items)
    return seller_id, len(items)

# Fixture pour nettoyer la base de données après les tests
@pytest.fixture(autouse=True)
def cleanup_db():
    yield
    db = get_test_db()
    db.items.delete_many({})

class TestPerformance:
    
    def test_pagination_performance(self, create_many_items):
        """Tester les performances de pagination avec beaucoup d'items"""
        _, total_items = create_many_items
        
        # Mesurer le temps pour la première page
        start_time = time.time()
        response = client.get("/api/items/?page=1&limit=10")
        first_page_time = time.time() - start_time
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 10
        assert data["total_items"] == total_items
        
        # Mesurer le temps pour une page au milieu
        start_time = time.time()
        response = client.get("/api/items/?page=5&limit=10")
        middle_page_time = time.time() - start_time
        
        assert response.status_code == 200
        
        # Mesurer le temps pour la dernière page
        last_page = (total_items + 9) // 10  # Arrondi supérieur
        start_time = time.time()
        response = client.get(f"/api/items/?page={last_page}&limit=10")
        last_page_time = time.time() - start_time
        
        assert response.status_code == 200
        
        # Afficher les temps de réponse pour analyse
        print(f"\nTemps de réponse pagination:")
        print(f"Première page: {first_page_time:.4f} secondes")
        print(f"Page du milieu: {middle_page_time:.4f} secondes")
        print(f"Dernière page: {last_page_time:.4f} secondes")
        
        # Vérifier que les temps de réponse sont raisonnables
        # Ces seuils peuvent être ajustés selon votre environnement
        assert first_page_time < 0.5
        assert middle_page_time < 0.5
        assert last_page_time < 0.5
    
    def test_search_performance(self, create_many_items):
        """Tester les performances de recherche"""
        _, _ = create_many_items
        
        # Mesurer le temps pour une recherche simple
        start_time = time.time()
        response = client.get("/api/items/?search=Produit")
        search_time = time.time() - start_time
        
        assert response.status_code == 200
        
        # Mesurer le temps pour une recherche avec filtres
        start_time = time.time()
        response = client.get("/api/items/?search=Produit&category=électronique&min_price=50&max_price=500")
        filtered_search_time = time.time() - start_time
        
        assert response.status_code == 200
        
        # Afficher les temps de réponse pour analyse
        print(f"\nTemps de réponse recherche:")
        print(f"Recherche simple: {search_time:.4f} secondes")
        print(f"Recherche filtrée: {filtered_search_time:.4f} secondes")
        
        # Vérifier que les temps de réponse sont raisonnables
        assert search_time < 0.5
        assert filtered_search_time < 0.5
    
    def test_sorting_performance(self, create_many_items):
        """Tester les performances de tri"""
        _, _ = create_many_items
        
        # Mesurer le temps pour un tri par prix croissant
        start_time = time.time()
        response = client.get("/api/items/?sort=price")
        asc_sort_time = time.time() - start_time
        
        assert response.status_code == 200
        
        # Mesurer le temps pour un tri par prix décroissant
        start_time = time.time()
        response = client.get("/api/items/?sort=-price")
        desc_sort_time = time.time() - start_time
        
        assert response.status_code == 200
        
        # Afficher les temps de réponse pour analyse
        print(f"\nTemps de réponse tri:")
        print(f"Tri croissant: {asc_sort_time:.4f} secondes")
        print(f"Tri décroissant: {desc_sort_time:.4f} secondes")
        
        # Vérifier que les temps de réponse sont raisonnables
        assert asc_sort_time < 0.5
        assert desc_sort_time < 0.5