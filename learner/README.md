# Learner - Fine-tuning SP2322

Pipeline de fine-tuning pour creer un modele de langage expert sur l'encaisseuse **SP2322** (Club Industries). Utilise Unsloth pour un entrainement optimise de Qwen3-1.7B sur un jeu de donnees technique de questions/reponses, produisant un modele GGUF deployable dans le systeme RAG.

## Concepts Théoriques

### 1. LLM & Architecture Transformer
Un **LLM (Large Language Model)** est un réseau de neurones profonds basé sur l'architecture **Transformer**. Sa fonction primaire est la modélisation du langage par le calcul de la probabilité conditionnelle du prochain token : $P(x_{t} | x_{1}, ..., x_{t-1})$.

*   **Mécanisme d'Attention (Self-Attention)** : Le cœur du Transformer. Il permet au modèle de pondérer l'importance de chaque mot dans une séquence par rapport aux autres via des matrices de **Query (Q)**, **Key (K)** et **Value (V)**. Le calcul de l'attention est défini par : $\text{Attention}(Q, K, V) = \text{softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right)V$.
*   **Tokens & Embeddings** : Le texte est fragmenté en tokens (sous-mots) puis projeté dans un espace vectoriel de haute dimension (embeddings), permettant de capturer les relations sémantiques complexes.
*   **Pré-entraînement (Causal LLM)** : Le modèle est entraîné de manière auto-supervisée sur des téraoctets de données pour minimiser la *cross-entropy loss*, développant ainsi une compréhension contextuelle massive.

### 2. Fine-Tuning Supervisé (SFT)
Le **SFT** consiste à ajuster les poids d'un modèle pré-entraîné sur un dataset étiqueté de paires instruction/réponse. Contrairement au pré-entraînement, l'objectif est d'aligner la distribution des sorties du modèle sur un domaine spécifique (ici, la maintenance industrielle).
*   **Transfer Learning** : On réutilise les connaissances générales (grammaire, logique) pour ne se concentrer que sur l'apprentissage des spécificités techniques.
*   **Lutte contre les hallucinations** : En restreignant l'espace de réponse au domaine de la SP2322, on augmente la "fidélité factualle" du modèle.

### 3. LoRA (Low-Rank Adaptation)
Pour éviter de modifier les milliards de paramètres du modèle (coûteux en VRAM), nous utilisons **LoRA**.
*   **Principe Mathématique** : On gèle les poids originaux $W_0$ et on injecte une mise à jour $\Delta W$ via deux matrices de bas rang $A$ et $B$ telles que $W = W_0 + AB$.
*   **Réduction de complexité** : Si $W$ est de dimension $d \times d$, on passe de $d^2$ paramètres à entraîner à $2 \times d \times r$, où $r$ (le rank) est très petit (ex: 32). Cela réduit le nombre de paramètres entraînables de >99% sans perte de performance notable.

### 4. Quantification & QLoRA
La **Quantification (NF4 - NormalFloat 4-bit)** est une technique de compression post-entraînement ou durant l'entraînement (QLoRA).
*   **Binarisation des poids** : On convertit les poids 16-bit (Float16) en 4-bit. Cela permet de charger un modèle de 1.7B paramètres dans moins de 2 GB de VRAM.
*   **Double Quantification** : Technique utilisée pour compresser les constantes de quantification elles-mêmes, optimisant encore plus l'empreinte mémoire.

### 5. Optimisation Unsloth
**Unsloth** optimise le pipeline d'entraînement via :
*   **Trition Kernels** : Réécriture manuelle des noyaux de calcul (Softmax, RoPE, LoRA) en langage Triton pour une exécution directe sur le matériel GPU.
*   **Moins de VRAM** : Utilisation de techniques de *Manual Backpropagation* pour libérer la mémoire des graphes de calcul intermédiaires plus rapidement.

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