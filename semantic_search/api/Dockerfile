# ============================================================================
# Stage 1: Construction et installation des dépendances
# ============================================================================
# Image de base optimisée pour uv avec Python 3.11 et Debian Bookworm
# - ghcr.io/astral-sh: Registry GitHub officiel d'Astral (créateurs de uv)
# - bookworm-slim: Debian 12 minimale (~150MB vs ~1GB pour l'image complète)
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

# Définit /app comme répertoire de travail pour toutes les commandes suivantes
# Crée automatiquement le dossier s'il n'existe pas
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

# Installation des outils de compilation nécessaires pour les extensions natives
# --mount=type=cache: Met en cache /var/cache/apt entre les builds
#   → Évite de retélécharger les index APT à chaque rebuild
#   → sharing=locked: Permet les builds parallèles sans corruption
# --no-install-recommends: Installe uniquement les paquets requis
#   → Réduit la taille de ~40% (pas de docs, suggestions, etc.)
# build-essential: Compilateurs C/C++ (gcc, g++, make)
#   → Requis pour compiler llama-cpp-python
# cmake: Système de build moderne pour projets C/C++
#   → Utilisé par llama-cpp-python pour configurer la compilation
# rm -rf /var/lib/apt/lists/*: Nettoie les métadonnées APT après installation
#   → Économise ~30MB dans l'image finale
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    && rm -rf /var/lib/apt/lists/*

# Copie des fichiers de métadonnées et installation des dépendances
# COPY nécessaire (pas --mount=type=bind) car pyproject.toml doit persister
# pour le second RUN qui installe le projet local
COPY pyproject.toml uv.lock README.md ./

# Installation des dépendances Python avec montage temporaire des fichiers
# --mount=type=cache: Cache UV (~500MB) persistant entre builds
#   → Évite de retélécharger les packages Python déjà récupérés
#   → Accélération drastique des rebuilds
# uv sync: Synchronise l'environnement virtuel avec uv.lock
#   --frozen: Mode strict, échoue si uv.lock est désynchronisé
#     → Garantit la reproductibilité (mêmes versions partout)
#     → Détecte les modifications non commitées du lockfile
#   --no-install-project: N'installe pas le projet local à cette étape
#     → Optimisation de cache : deps changent moins souvent que le code
#     → Permet de reconstruire uniquement la dernière layer si code modifié
#   --no-dev: Exclut les dépendances de développement (pytest, ruff, etc.)
#   --all-extras: Installe toutes les dépendances optionnelles du projet
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev --all-extras

# Copie du code source dans l'image de build
# COPY vs --mount=type=bind: Ici on DOIT copier car le code sera dans l'image finale
# ./src: Contient le code applicatif Python
COPY src ./src

# Installation finale du projet local
# Génère les scripts d'entrée définis dans pyproject.toml [project.scripts]
# Sans --no-install-project cette fois : installe le package en mode "editable"
# Le cache UV est réutilisé : seules les nouvelles dépendances sont téléchargées
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --all-extras

# ============================================================================
# Stage 2: Image d'exécution minimale (runtime)
# ============================================================================
# Image Python officielle Debian Bookworm slim (~150MB)
# Séparation builder/runtime → image finale sans outils de compilation (~70% plus petite)
FROM python:3.11-slim-bookworm

WORKDIR /app

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
RUN groupadd -r appuser -g 1000 && \
    useradd -r -u 1000 -g appuser -m -s /sbin/nologin appuser

# Copie de l'environnement virtuel depuis le stage builder
# --from=builder: Récupère depuis l'image de build (multi-stage)
#   → Environnement complet avec toutes les dépendances installées
#   → Pas d'outils de compilation (build-essential, cmake) dans l'image finale
# --chown=appuser:appuser: Définit le propriétaire dès la copie
#   → Évite un `chown` séparé = une layer en moins
#   → Optimisation: propriété correcte dès la création
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

# Création des répertoires applicatifs avec permissions appropriées
# mkdir -p: Crée les dossiers parents si nécessaires (-p = parents)
# /app/logs: Pour les fichiers de log de l'application
#   → Montable en volume pour persistance
#   → Séparé de /app pour faciliter la rotation des logs
# /app/data: Pour les données persistantes (DB SQLite, uploads, cache)
#   → Point de montage standard pour volumes Docker
# /home/appuser/.cache: Pour les modèles Hugging Face et Sentence Transformers
#   → Nécessaire pour que les bibliothèques puissent télécharger et cacher les modèles
# chown -R: Change récursivement le propriétaire
#   → L'utilisateur appuser peut écrire dans ces dossiers
#   → -R inclut tous les sous-dossiers futurs
RUN mkdir -p /app/logs /app/data /app/models /home/appuser/.cache && \
    chown -R appuser:appuser /app /home/appuser/.cache

# Copie du code source de l'application
# Séparé de la copie du .venv pour optimiser le cache Docker
#   → Si le code change, seulement cette layer est reconstruite
#   → Les dépendances (layer précédente) restent en cache
# --chown: Propriété immédiate pour éviter layer supplémentaire
COPY --chown=appuser:appuser src/ /app/src/
COPY --chown=appuser:appuser pyproject.toml /app/

# Bascule sur l'utilisateur non-root pour l'exécution
# Toutes les commandes suivantes (CMD) s'exécutent en tant que appuser
# Sécurité: le processus applicatif n'a PAS les droits root
#   → Isolation : ne peut pas modifier les fichiers système
#   → Compliance : requis par de nombreuses normes (PCI-DSS, SOC2)
#   → Kubernetes SecurityContext: compatible avec runAsNonRoot=true
USER appuser

# Commande par défaut au démarrage du conteneur
# "api": Script défini dans pyproject.toml [project.scripts]
#   → Généré automatiquement par uv/pip lors de l'installation
#   → Équivalent à exécuter le point d'entrée de l'application
# Forme exec (liste): Recommandée pour gestion correcte des signaux
#   → SIGTERM/SIGINT transmis directement au processus Python
#   → Shutdown gracieux (fermeture connexions DB, flush logs)
# Alternative forme shell: CMD api
#   → Utilise /bin/sh -c "api" → processus PID 1 = shell, pas Python
#   → Mauvaise gestion des signaux (dangereux en production)
CMD ["api"]