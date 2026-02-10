# Multi-stage build pour optimiser la taille de l'image finale et garantir un environnement propre pour l'exécution de l'application.
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

# Dossier de travail dans le conteneur de build pour installer les dépendances
WORKDIR /app

# Activer la compilation du bytecode pour améliorer les performances d'exécution et réduire la taille de l'image finale en évitant les fichiers .pyc inutiles.
ENV UV_COMPILE_BYTECODE=1

# Copier uniquement les fichiers nécessaires à l'installation
COPY pyproject.toml uv.lock ./

# Installer les dépendances dans un environnement virtuel isolé pour éviter les conflits et garantir que seules les dépendances nécessaires sont incluses dans l'image finale.
# -- `--frozen` : Assure que les dépendances sont installées exactement comme spécifié dans le fichier de verrouillage, garantissant la reproductibilité.
# -- `--no-install-project` : Empêche l'installation du projet lui-même, ce qui est inutile dans cette étape de build et permet de réduire la taille de l'image finale.
# -- `--no-dev` : Exclut les dépendances de développement, ce qui est crucial pour minimiser la surface d'attaque et la taille de l'image finale.
RUN uv sync --frozen --no-install-project --no-dev

# =============================================================================
# Stage 2: Image d'exécution minimale
# =============================================================================
# Utiliser une image de base plus légère pour l'exécution, réduisant ainsi la taille finale de l'image et minimisant les vulnérabilités potentielles.
FROM python:3.11-slim-bookworm

# Mise à jour et installation des dépendances nécessaires pour l'exécution de l'application, tout en nettoyant les caches pour réduire la taille de l'image finale.
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# On crée un utilisateur non-root pour exécuter l'application, ce qui est une bonne pratique de sécurité pour limiter les permissions et réduire les risques en cas de compromission.
RUN groupadd -r ingestuser && \
    useradd -r -g ingestuser -u 1001 -m -s /bin/bash ingestuser

# Copier les dépendances installées depuis le conteneur de build vers l'image d'exécution, assurant que seules les dépendances nécessaires sont incluses, ce qui réduit la taille de l'image finale et améliore la sécurité.
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Définir le répertoire de travail pour l'application, garantissant que tous les fichiers nécessaires sont accessibles et que les commandes s'exécutent dans le bon contexte.
WORKDIR /app

# Copier le code de l'application en définissant le propriétaire sur l'utilisateur non-root pour maintenir les bonnes pratiques de sécurité.
COPY --chown=ingestuser:ingestuser . /app/

# Changer l'utilisateur pour exécuter l'application avec des permissions limitées.
USER ingestuser

# Exécuter l'ingestion en utilisant le script python écrit et installé
CMD ["ingest"]
