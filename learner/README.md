# Learner - Fine-tuning SP2322

Ce dossier contient les scripts et ressources nécessaires pour l'entraînement d'un modèle de langage expert sur l'encaisseuse **SP2322**.

## Structure du projet

- `finetune_sp2322.py` : Script principal d'entraînement utilisant **Unsloth**.
- `download_model.py` : Script utilitaire pour pré-télécharger le modèle de base avec barre de progression.
- `finetune_sp2322.jsonl` : Jeu de données d'entraînement.
- `pyproject.toml` : Gestion des dépendances via `uv`.

## Installation

Assurez-vous d'avoir Python 3.10+ et un GPU compatible CUDA (ex: RTX 3000, T4).

```powershell
# Installation des dépendances
uv sync
```

## Utilisation

### 1. Pré-téléchargement du modèle
Indispensable pour éviter les "freezes" d'interface et gérer les limites de chemins Windows.
```powershell
uv run download_model.py
```

### 2. Lancement du Fine-tuning
L'entraînement dure environ 10-15 minutes sur une RTX 3000.
```powershell
uv run finetune_sp2322.py
```

## Résultats attendus

Après l'entraînement, deux dossiers sont générés :
- `sp2322_lora/` : Adaptateurs légers pour recharger le modèle sous Python.
- `sp2322_gguf/` : Modèle quantifié (Q4_K_M) prêt pour la production (Ollama, llama.cpp, ou votre API RAG).

## Notes spécifiques Windows

Le script inclut des correctifs automatiques pour :
- **WinError 1314** : Désactivation des liens symboliques HuggingFace.
- **MAX_PATH (260 char)** : Déplacement des caches Triton/Inductor vers `~/.tc` et `~/.ic`.
