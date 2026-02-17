# ============================================================================
# Stage 1: Construction et installation des dépendances
# ============================================================================
# Image de base optimisée pour uv avec Python 3.11 et Debian Bookworm
# - ghcr.io/astral-sh: Registry GitHub officiel d'Astral (créateurs de uv)
# - bookworm-slim: Debian 12 minimale (~150MB vs ~1GB pour l'image complète)
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

# Définit /app comme répertoire de travail pour toutes les commandes suivantes
# Toutes les opérations COPY, RUN, etc. s'exécutent relativement à ce chemin
# mkdir automatique: Docker crée le dossier s'il n'existe pas
WORKDIR /app

# Configuration des variables d'environnement pour uv
# UV_COMPILE_BYTECODE=1: Précompile le code Python en bytecode (.pyc)
#   → Améliore les performances au démarrage
#   → Réduit la taille finale car pas de génération à l'exécution
# UV_LINK_MODE=copy: Force la copie des fichiers au lieu de liens symboliques
#   → Essentiel pour le multi-stage build (liens cassés entre stages)
#   → Nécessaire avec un utilisateur non-root (permissions cohérentes)
# UV_NO_PROGRESS=1: Désactive les barres de progression dans les logs
#   → Logs plus propres en CI/CD (pas de rafraîchissement de lignes)
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_PROGRESS=1

# Copie des fichiers de métadonnées et installation des dépendances
# COPY nécessaire (pas --mount=type=bind) car pyproject.toml doit persister
# pour le second RUN qui installe le projet local
COPY pyproject.toml uv.lock README.md ./

# Installation des dépendances Python avec montage temporaire des fichiers
# --mount=type=cache: Cache UV (~500MB) persistant entre builds
#   → Évite de retélécharger les packages Python déjà récupérés
#   → Accélération drastique des rebuilds
# uv sync: Synchronise l'environnement virtuel avec uv.lock
# --no-install-project: N'installe pas le projet local à cette étape
#   → Optimisation de cache : deps changent moins souvent que le code
#   → Permet de reconstruire uniquement la dernière layer si code modifié
# --no-dev: Exclut les dépendances de développement (pytest, ruff, etc.)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-install-project --no-dev

# Copie du code source dans l'image de build
# COPY vs --mount=type=bind: Ici on DOIT copier car le code sera dans l'image finale
# ./src: Contient le code applicatif Python
COPY src ./src

# Installation finale du projet local
# Génère les scripts d'entrée définis dans pyproject.toml [project.scripts]
# Sans --no-install-project cette fois : installe le package en mode "editable"
# Le cache UV est réutilisé : seules les nouvelles dépendances sont téléchargées
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev

# ============================================================================
# Stage 2: Image d'exécution minimale (runtime)
# ============================================================================
# Image Python officielle Debian Bookworm slim (~150MB)
# Séparation builder/runtime → image finale sans outils de compilation (~70% plus petite)
FROM python:3.11-slim-bookworm

# Configuration Python pour environnement de production
# PYTHONUNBUFFERED=1: Force le mode non-bufferisé pour stdout/stderr
#   → Logs en temps réel dans Docker/Kubernetes (sinon buffer de 4-8KB)
#   → CRITIQUE pour le debugging : logs visibles immédiatement
#   → Nécessaire pour les health checks et crash reports
# PYTHONDONTWRITEBYTECODE=1: Désactive la génération de fichiers .pyc
#   → Redondant car déjà compilés dans le builder (UV_COMPILE_BYTECODE=1)
#   → Évite l'écriture inutile sur disque (performance en lecture seule)
#   → Utile si volumes montés en read-only
# PYTHONPATH="/app/src": Ajoute /app/src au chemin de recherche des modules
#   → Permet les imports absolus: `from mon_module import X`
#   → Évite les imports relatifs compliqués (../../..)
# PATH="/app/.venv/bin:$PATH": Ajoute les binaires de l'env virtuel au PATH
#   → Permet d'exécuter directement `api` au lieu de `/app/.venv/bin/api`
#   → Les commandes Python utilisent l'env virtuel par défaut
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH="/app/src" \
    PATH="/app/.venv/bin:$PATH"

# Mise à jour système et installation des dépendances runtime critiques
# STRATÉGIE: Un seul RUN pour minimiser les layers Docker
# apt-get update: Rafraîchit les index des paquets disponibles
# apt-get upgrade -y: Met à jour TOUS les paquets installés
# apt-get install -y --no-install-recommends:
#   -y: Mode non-interactif (accepte automatiquement)
#   --no-install-recommends: Installe UNIQUEMENT dépendances strictes
#     → Exclut: Suggestions, docs, man pages, locales
# ca-certificates: Autorités de certification SSL/TLS racines
# libgomp1: OpenMP runtime pour Docling (parallélisation)
# libgl1: OpenGL pour traitement d'images par Docling
# libglib2.0-0: GLib pour certaines bibliothèques graphiques
# libnuma1: Bibliothèque pour la gestion de la mémoire NUMA (utilisée par PyTorch)
# tesseract-ocr: Moteur OCR pour extraction de texte des images/PDF scannés
# tesseract-ocr-fra: Données linguistiques françaises pour Tesseract
# tesseract-ocr-eng: Données linguistiques anglaises pour Tesseract
# rm -rf /var/lib/apt/lists/*: Nettoie métadonnées APT après installation
# apt-get clean: Nettoie le cache APT des .deb téléchargés
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        libgomp1 \
        libnuma1 \
        libgl1 \
        libglib2.0-0 \
        tesseract-ocr \
        tesseract-ocr-fra \
        tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Création d'un utilisateur non-root pour l'exécution
# Sécurité: principe du moindre privilège (least privilege)
#   → Si conteneur compromis, attaquant n'est pas root
#   → Limite les dégâts possibles (pas d'accès système)
# groupadd -r: Crée un groupe système (-r = UID < 1000)
#   -g 1000: GID fixe pour compatibilité avec volumes montés
# useradd -r: Crée un utilisateur système
#   -u 1000: UID fixe (évite les conflits de permissions avec l'hôte)
#   -g appuser: Groupe principal
#   -m: Crée le home directory (/home/appuser)
#   -s /sbin/nologin: Pas de shell interactif (sécurité++)
# UID/GID 1000: Convention pour le premier utilisateur non-système
#   → Compatible avec la plupart des systèmes Linux
#   → Facilite le montage de volumes (permissions cohérentes)
RUN groupadd -r ingestuser -g 1000 && \
    useradd -r -g ingestuser -u 1000 -m -s /sbin/nologin ingestuser


# Création des répertoires applicatifs avec permissions appropriées
# Crée aussi le répertoire .cache pour les modèles Hugging Face et Sentence Transformers
# /docling_cache pour les modèles Docling (layout detection, OCR)
# /app/models est créé ici pour que Docker initialise le volume nommé avec les bonnes permissions
RUN mkdir -p /app/logs /app/data /app/models /home/ingestuser/.cache /docling_cache && \
    chown -R ingestuser:ingestuser /app /home/ingestuser/.cache /docling_cache

# Copie de l'environnement virtuel depuis le stage builder
# --from=builder: Référence le stage nommé "builder" (multi-stage build)
# --chown=ingestuser:ingestuser: Définit propriétaire ET groupe immédiatement
COPY --from=builder --chown=ingestuser:ingestuser /app/.venv /app/.venv

# Définition du répertoire de travail pour l'application
WORKDIR /app

# Copie sélective du code source avec ownership approprié
COPY --chown=ingestuser:ingestuser src/ /app/src/
COPY --chown=ingestuser:ingestuser pyproject.toml /app/

# Basculement vers l'utilisateur non-root pour toute exécution
USER ingestuser

# Commande par défaut au démarrage du conteneur
# "ingest": Script défini dans pyproject.toml [project.scripts]
#   → Généré automatiquement par uv/pip lors de l'installation
#   → Équivalent à exécuter le point d'entrée de l'application
# Forme exec (liste): Recommandée pour gestion correcte des signaux
#   → SIGTERM/SIGINT transmis directement au processus Python
#   → Shutdown gracieux (fermeture connexions DB, flush logs)
# Alternative forme shell: CMD ingest
#   → Utilise /bin/sh -c "ingest" → processus PID 1 = shell, pas Python
#   → Mauvaise gestion des signaux (dangereux en production)
CMD ["ingest"]