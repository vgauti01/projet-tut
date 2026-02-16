# Learner - Fine-tuning SP2322

Pipeline de fine-tuning pour creer un modele de langage expert sur l'encaisseuse **SP2322** (Club Industries). Utilise Unsloth pour un entrainement optimise de Qwen3-1.7B sur un jeu de donnees technique de questions/reponses, produisant un modele GGUF deployable dans le systeme RAG.

## Structure du projet

```
learner/
├── finetune_sp2322.py       # Script principal d'entrainement
├── finetune_sp2322.jsonl    # Jeu de donnees (182 paires Q/R)
├── download_model.py        # Pre-telechargement du modele de base
├── main.py                  # Point d'entree (placeholder)
├── pyproject.toml           # Dependances (uv)
├── llama.cpp/               # Sous-module pour conversion GGUF
│
├── sp2322_lora/             # (genere) Adaptateurs LoRA (~133 MB)
└── sp2322_gguf/             # (genere) Modele quantifie GGUF (~1.1 GB)
```

## Prerequis

- Python 3.13+
- GPU compatible CUDA (RTX 3000+, T4, etc.) avec 8 GB+ VRAM
- ~20 GB d'espace disque (modeles, caches, sorties)
- [uv](https://docs.astral.sh/uv/) comme gestionnaire de paquets

## Installation

```bash
cd learner
uv sync
```

## Utilisation

### 1. Pre-telechargement du modele

Indispensable pour eviter les "freezes" d'interface et afficher une barre de progression.

```bash
uv run download_model.py
```

Telecharge `unsloth/Qwen3-1.7B-unsloth-bnb-4bit` (~4 GB) dans le cache HuggingFace.

### 2. Lancement du fine-tuning

```bash
uv run finetune_sp2322.py
```

Duree estimee : 10-15 minutes sur une RTX 3000.

### 3. Resultats

Deux dossiers sont generes apres l'entrainement :

| Sortie | Taille | Usage |
|--------|--------|-------|
| `sp2322_lora/` | ~133 MB | Adaptateurs LoRA pour recharger en Python (reprise d'entrainement) |
| `sp2322_gguf/Sp2322_Gguf-1.7B-Q4_K_M.gguf` | ~1.1 GB | Modele quantifie pour production (llama.cpp, Ollama, API RAG) |

## Jeu de donnees

Le fichier `finetune_sp2322.jsonl` contient **182 paires Q/R** au format ChatML :

```json
{
  "messages": [
    {"role": "system", "content": "Tu es un assistant technique expert de l'encaisseuse SP2322..."},
    {"role": "user", "content": "Quel est le role de l'encaisseuse SP2322 ?"},
    {"role": "assistant", "content": "L'encaisseuse SP2322 (aussi appelee Encaisseuse Club)..."}
  ]
}
```

Couvre : description de la machine, composants, conditions d'exploitation, depannage, maintenance, parametres techniques, securite.

## Configuration

Les parametres principaux sont dans `finetune_sp2322.py` :

### Modele

| Parametre | Valeur | Description |
|-----------|--------|-------------|
| `MAX_SEQ_LENGTH` | 2048 | Longueur max en tokens |
| `load_in_4bit` | true | Quantification 4-bit (economie VRAM) |

### LoRA

| Parametre | Valeur | Description |
|-----------|--------|-------------|
| `r` | 32 | Rang des adaptateurs (plus haut = plus de parametres) |
| `lora_alpha` | 32 | Facteur de mise a l'echelle |
| `target_modules` | q/k/v/o_proj, gate/up/down_proj | Couches adaptees |

### Entrainement

| Parametre | Valeur | Description |
|-----------|--------|-------------|
| `num_train_epochs` | 6 | Nombre de passes sur le dataset |
| `per_device_train_batch_size` | 2 | Taille du batch par GPU |
| `gradient_accumulation_steps` | 4 | Batch effectif = 8 |
| `learning_rate` | 2e-4 | Taux d'apprentissage |
| `lr_scheduler_type` | cosine | Planification du learning rate |
| `weight_decay` | 0.01 | Regularisation L2 |
| `warmup_steps` | 5 | Montee progressive du LR |

### Export GGUF

| Parametre | Valeur | Description |
|-----------|--------|-------------|
| `quantization_method` | q4_k_m | Quantification recommandee pour production |

Autres options : `q8_0` (meilleure qualite, ~2-3 GB), `q6_k`, `f16` (pleine precision).

## Integration avec le systeme RAG

1. Copier le modele GGUF :
```bash
cp sp2322_gguf/Sp2322_Gguf-1.7B-Q4_K_M.gguf ../semantic_search/data/models/
```

2. Configurer dans `semantic_search/.env` :
```bash
LLM_MODEL_PATH=/app/models/Sp2322_Gguf-1.7B-Q4_K_M.gguf
LLM_N_CTX=8192
```

3. Redemarrer l'API :
```bash
cd ../semantic_search && docker compose up -d api
```

## Notes specifiques Windows

Le script inclut des correctifs automatiques pour :

| Probleme | Correctif |
|----------|-----------|
| **WinError 1314** (liens symboliques) | `HF_HUB_DISABLE_SYMLINKS=1` |
| **MAX_PATH (260 char)** | Caches Triton/Inductor deplaces vers `~/.tc` et `~/.ic` |
| **Conversion GGUF echoue** | Utiliser les binaires pre-compiles dans `llama-b8067-bin-win-cuda-13.1-x64/` |

## Depannage

| Probleme | Solution |
|----------|----------|
| OutOfMemory (OOM) | Reduire `per_device_train_batch_size` a 1, ou `r` a 16 |
| Entrainement tres lent | Verifier la presence du GPU avec `nvidia-smi` |
| Conversion GGUF echoue | Utiliser `llama-quantize.exe` manuellement (voir sortie du script) |
| Freeze au telechargement | Lancer `download_model.py` separement |

## Stack technique

- **Unsloth** : Entrainement optimise (2x plus rapide, 30% VRAM en moins)
- **Qwen3-1.7B** : Modele de base (4-bit via bitsandbytes)
- **PyTorch** + CUDA : Backend d'entrainement
- **TRL (SFTTrainer)** : Supervised Fine-Tuning avec masquage des reponses
- **PEFT** : Parameter Efficient Fine-Tuning (LoRA)
- **llama.cpp** : Conversion et inference GGUF
- **uv** : Gestionnaire de paquets Python