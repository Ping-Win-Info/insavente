FROM python:3.9-slim

WORKDIR /app

# Copier les fichiers de dépendances
COPY requirements.txt .

# Installer les dépendances
RUN pip install -r requirements.txt

# Copier tout le code source
COPY . .

# S'assurer que le dossier app est dans le PYTHONPATH
ENV PYTHONPATH="${PYTHONPATH}:/app"

# Exposer le port utilisé par FastAPI
EXPOSE 8000

# Commande par défaut (peut être remplacée dans docker-compose)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]