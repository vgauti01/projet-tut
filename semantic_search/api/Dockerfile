# Stage 1: Build & Lock
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

# Dossier de travail dans le conteneur de build pour installer les dépendances
WORKDIR /app

# Activer la compilation du bytecode pour améliorer les performances d'exécution et réduire la taille de l'image finale en évitant les fichiers .pyc inutiles.
ENV UV_COMPILE_BYTECODE=1
# Utiliser le mode de lien "copy" pour éviter les problèmes de permissions et garantir que les fichiers sont copiés dans l'image finale, ce qui est particulièrement important lorsque l'on utilise un utilisateur non-root pour exécuter l'application.
ENV UV_LINK_MODE=copy

# Installer les dépendances requises pour le build (llama-cpp-python nécessite cmake et build-essential pour la compilation des extensions C++)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    && rm -rf /var/lib/apt/lists/*

# Au lieu de copier les fichiers, on les montes temporairement pour éviter de les inclure dans l'image finale.
# - `--mount=type=cache` : Permet de mettre en cache les dépendances téléchargées, ce qui accélère les builds successifs.
# - `--mount=type=bind` : end les fichiers pyproject.toml et uv.lock visibles pour la commande sans les copier définitivement dans le système de fichiers du conteneur à cette étape.
# - `uv sync --frozen --no-install-project --no-dev --all-extras` : Installe les dépendances.
#  - `--frozen` : Assure que les dépendances sont installées exactement comme spécifié dans le fichier de verrouillage, garantissant la reproductibilité.
#  - `--no-install-project` : Empêche l'installation du projet lui-même, ce qui est inutile dans cette étape de build et permet de réduire la taille de l'image finale.
#  - `--no-dev` : Exclut les dépendances de développement, ce qui est crucial pour minimiser la surface d'attaque et la taille de l'image finale.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --frozen --no-install-project --no-dev --all-extras

# Stage 2: Image d'exécution minimale
FROM python:3.11-slim-bookworm

# Dossier de travail pour l'application dans le conteneur
WORKDIR /app

# Copier l'environnement virtuel depuis l'étape de build
COPY --from=builder /app/.venv /app/.venv
# Ajouter le chemin de l'environnement virtuel au PATH pour que les commandes installées soient accessibles.
ENV PATH="/app/.venv/bin:$PATH"

# Création d'un utilisateur non-root pour exécuter l'application
# ce qui est une bonne pratique de sécurité pour limiter les permissions et réduire les risques en cas de compromission.
RUN groupadd -r appuser && useradd -r -g appuser -u 1000 -m appuser
# On crée un dossier pour les logs et on attribue les permissions à l'utilisateur non-root pour garantir que l'application puisse écrire les logs sans problèmes de permissions, tout en maintenant une bonne sécurité.
RUN mkdir -p /app/logs && chown appuser:appuser /app/logs

# Copier le code de l'application en définissant le propriétaire sur l'utilisateur non-root pour maintenir les bonnes pratiques de sécurité.
# Cela garantit que les fichiers de l'application sont accessibles à l'utilisateur non-root et que les permissions sont correctement configurées, ce qui est crucial pour la sécurité de l'application.
COPY --chown=appuser:appuser src/ /app/src/
COPY --chown=appuser:appuser pyproject.toml /app/

# Cette variable d'environnement est utilisée pour s'assurer que Python peut trouver les modules de l'application
# en particulier si l'application est structurée de manière à ce que le code source soit dans un sous-répertoire (comme "src").
# En définissant PYTHONPATH sur "/app/src", on garantit que les imports dans le code de l'application fonctionnent correctement, même si l'on exécute des commandes depuis le répertoire racine (/app).
ENV PYTHONPATH="/app/src"

# On change l'utilisateur pour exécuter l'application avec des permissions limitées.
USER appuser

# Run the API using the entry point defined in pyproject.toml
CMD ["api"]
