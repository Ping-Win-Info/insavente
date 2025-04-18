# Insa-Vente


sudo docker compose up --build [-d]


## Tests
sudo docker compose exec api pytest --cov=app --cov-report=term

## Fonctionnalités implémentées

### Gestion des articles

- **Création d'articles** : Permettre aux utilisateurs authentifiés de créer des articles à vendre
- **Récupération d'articles** : Lister tous les articles disponibles, avec pagination
- **Filtrage avancé** : 
  - Par catégorie
  - Par plage de prix (min/max)
  - Par texte (recherche dans titre et description)
- **Tri des résultats** :
  - Par prix (croissant/décroissant)
  - Par date (plus récents/plus anciens)
- **Détails d'un article** : Récupérer les informations détaillées d'un article spécifique
- **Mise à jour d'articles** : Permettre aux propriétaires de modifier leurs articles
- **Suppression d'articles** : Permettre aux propriétaires de supprimer leurs articles
- **Désactivation d'articles** : Possibilité de marquer un article comme inactif sans le supprimer

### Authentification et gestion utilisateurs

- **Inscription** : Création de compte utilisateur avec validation de données
- **Connexion** : Authentification et génération de token JWT
- **Profil utilisateur** : Récupération et mise à jour des informations de profil
- **Changement de mot de passe** : Possibilité de modifier son mot de passe

### Sécurité

- **Authentification par JWT** : Protection des routes sensibles
- **Validation des droits** : Vérification que l'utilisateur est propriétaire avant modification/suppression
- **Hachage des mots de passe** : Stockage sécurisé des mots de passe avec bcrypt
- **Validation de données** : Vérification de l'intégrité des données entrantes

## API Endpoints

### Gestion des articles

- `POST /api/items/` : Créer un nouvel article
- `GET /api/items/` : Récupérer la liste des articles avec filtrage et pagination
- `GET /api/items/{item_id}` : Récupérer un article spécifique
- `PUT /api/items/{item_id}` : Mettre à jour un article
- `DELETE /api/items/{item_id}` : Supprimer un article

### Authentification et utilisateurs

- `POST /api/auth/register` : Inscrire un nouvel utilisateur
- `POST /api/auth/login` : Se connecter et obtenir un token JWT
- `GET /api/auth/me` : Récupérer les informations de l'utilisateur connecté
- `PUT /api/auth/me` : Mettre à jour le profil utilisateur
- `POST /api/auth/change-password` : Modifier le mot de passe

## Tests automatisés

L'application est testée avec Pytest et inclut plusieurs types de tests :

### Tests de fonctionnalités de base
- Tests CRUD complets pour les articles
- Tests d'authentification et de gestion des utilisateurs

### Tests avancés
- Validation des données et cas limites
- Filtrage et recherche avancés
- Gestion des erreurs (ID invalides, JSON malformé, etc.)
- Tests de sécurité (tokens expirés, droits d'accès, etc.)

### Tests de performance
- Pagination avec grand volume de données
- Performance des fonctionnalités de recherche et de tri


## Licence

Ce projet est sous licence GNU GPL v3.0.