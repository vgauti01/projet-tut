# -*- coding: utf-8 -*-
"""
Fine-tuning Qwen3-1.7B pour l'encaisseuse SP2322
================================================
Script adapte du notebook Unsloth pour entrainer un modele expert en depannage
et assistance technique sur la machine SP2322 (encaisseuse club).
Le modele 1.7B est choisi pour sa rapidite et sa faible consommation memoire,
sans le mode "thinking" pour des reponses directes.

Licence : LGPL-3.0 (Unsloth)
"""


# =============================================================================
# 1. CHARGEMENT DU MODELE DE BASE
# =============================================================================
# On charge Qwen3-1.7B en quantification 4 bits. Ce modele tres leger (1.7B)
# tourne facilement sur n'importe quel GPU moderne et meme certains CPU.

print("Initialisation du chargement du modèle...")
print("Note : Si le modèle n'est pas déjà dans le cache, le téléchargement peut sembler figé.")
print("Vous pouvez lancer 'python download_model.py' au préalable pour voir la progression.")

import os
# Désactive les liens symboliques sur Windows pour éviter l'erreur de privilèges [WinError 1314]
# DOIT ETRE FAIT AVANT L'IMPORT DE UNSLOTH/HUGGINGFACE
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"
# Optionnel : Accélère les téléchargements HuggingFace si hf-transfer est installé
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"

from unsloth import FastLanguageModel
import torch

# Correction pour Triton/Inductor sur Windows (évite les erreurs de chemin trop long dans AppData)
short_cache_base = os.path.join(os.path.expanduser("~"), ".tc") 
os.environ["TRITON_CACHE_DIR"] = short_cache_base
os.environ["TORCHINDUCTOR_CACHE_DIR"] = os.path.join(os.path.expanduser("~"), ".ic")

# Longueur maximale des sequences en tokens.
# 2048 est suffisant pour nos Q/R techniques (rarement > 1000 tokens).
# Augmenter a 4096 si les reponses sont tres longues.
MAX_SEQ_LENGTH = 2048

print("Chargement du modèle de base Qwen3-1.7B en quantification 4 bits...")
model, tokenizer = FastLanguageModel.from_pretrained(
    # On utilise explicitement la version bnb-4bit pour éviter un téléchargement caché
    model_name = "unsloth/Qwen3-1.7B-unsloth-bnb-4bit",

    max_seq_length = MAX_SEQ_LENGTH,

    # Quantification 4 bits : reduit la memoire de ~16 Go a ~4 Go.
    # Tres peu de perte de qualite grace a la quantification dynamique.
    load_in_4bit = True,

    # Mettre a True pour quantification 8 bits (plus precis, mais 2x la memoire).
    load_in_8bit = False,

    # False = on utilise LoRA (adaptateurs legers) au lieu d'entrainer
    # tous les parametres. Beaucoup plus rapide et economique.
    full_finetuning = False,

    # Decommentez et renseignez votre token HuggingFace si le modele est restreint.
    # token = "hf_VotreToken",
)
print("Modèle et Tokenizer chargés avec succès.")


# =============================================================================
# 2. CONFIGURATION DES ADAPTATEURS LoRA
# =============================================================================
# LoRA (Low-Rank Adaptation) ajoute de petites matrices entrainables aux
# couches du modele. On n'entraine que ~1-2% des parametres au lieu de 100%,
# ce qui est beaucoup plus rapide et necessite peu de VRAM.

model = FastLanguageModel.get_peft_model(
    model,

    # Rang LoRA : plus c'est eleve, plus le modele peut apprendre de choses,
    # mais plus ca coute en memoire. 32 est un compromis.
    r = 32,

    # Couches ciblees par LoRA : on entraine les projections d'attention
    # (q, k, v, o) et les couches feed-forward (gate, up, down).
    # C'est la configuration standard recommandee par Unsloth.
    target_modules = [
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj",
    ],

    # Alpha LoRA : facteur de mise a l'echelle. Regle empirique : alpha = r.
    lora_alpha = 32,

    # Dropout LoRA : 0 est optimise par Unsloth (pas de regularisation).
    # Avec un petit dataset, vous pouvez essayer 0.05 pour eviter l'overfitting.
    lora_dropout = 0,

    # Pas de biais entraine (optimise par Unsloth).
    bias = "none",

    # "unsloth" active le gradient checkpointing optimise :
    # economise ~30% de VRAM en recalculant les activations au lieu
    # de les stocker en memoire.
    use_gradient_checkpointing = "unsloth",

    # Graine aleatoire pour la reproductibilite.
    random_state = 3407,

    # Rank-Stabilized LoRA : pas necessaire pour notre cas.
    use_rslora = False,
    loftq_config = None,
)


# =============================================================================
# 3. PREPARATION DES DONNEES
# =============================================================================
# On charge notre dataset JSONL de questions/reponses sur l'encaisseuse SP2322.
# Chaque ligne contient : {"messages": [system, user, assistant]}
#
# Le format Qwen3 utilise le template ChatML :
#   <|im_start|>system
#   Tu es un assistant technique...
#   <|im_end|>
#   <|im_start|>user
#   Comment consigner la machine ?
#   <|im_end|>
#   <|im_start|>assistant
#   Pour consigner l'encaisseuse SP2322...
#   <|im_end|>

from unsloth.chat_templates import get_chat_template

# On applique le template de chat Qwen3 au tokenizer.
# On utilise le template standard "qwen3" car notre dataset ne contient pas
# de blocs <think>. Le modele n'utilisera PAS ses capacites de raisonnement 'thinking'
# pour rester concis et rapide.
tokenizer = get_chat_template(
    tokenizer,
    chat_template = "qwen3",
)

import json
from datasets import Dataset

# Chargement du fichier JSONL local
DATASET_PATH = "finetune_sp2322.jsonl"

conversations_list = []
with open(DATASET_PATH, "r", encoding="utf-8") as f:
    for line in f:
        entry = json.loads(line)
        # Chaque entree a un champ "messages" avec [system, user, assistant].
        # On le renomme en "conversations" pour le pipeline Unsloth.
        conversations_list.append(entry["messages"])

# Conversion en objet Dataset de HuggingFace (necessaire pour le trainer).
dataset = Dataset.from_dict({"conversations": conversations_list})

print(f"Dataset charge : {len(dataset)} exemples d'entrainement")


# =============================================================================
# 4. APPLICATION DU TEMPLATE DE CHAT
# =============================================================================
# On convertit chaque conversation en texte formate selon le template ChatML
# de Qwen3. Le trainer utilisera ce texte pour l'entrainement.

def formatting_prompts_func(examples):
    """Applique le template de chat Qwen3 a chaque conversation."""
    convos = examples["conversations"]
    texts = [
        tokenizer.apply_chat_template(
            convo,
            tokenize=False,              # Retourne du texte, pas des tokens
            add_generation_prompt=False,  # Pas de prompt de generation (on entraine)
            enable_thinking=False,         # Pas de tokens de thinking (on veut des reponses directes)
        )
        for convo in convos
    ]
    return {"text": texts}

dataset = dataset.map(formatting_prompts_func, batched=True)

# Verification : affiche le premier exemple formate pour verifier
# que le template est correctement applique.
print("\n--- Apercu du premier exemple formate ---")
print(dataset[0]["text"][:500])
print("...")


# =============================================================================
# 5. CONFIGURATION DE L'ENTRAINEMENT
# =============================================================================
# On utilise SFTTrainer (Supervised Fine-Tuning) de la bibliotheque TRL.

from trl import SFTTrainer, SFTConfig

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    eval_dataset=None,  # Pas d'evaluation separee (dataset trop petit pour split)
    args=SFTConfig(
        # Champ contenant le texte formate a utiliser pour l'entrainement.
        dataset_text_field="text",

        # Taille du batch par GPU. 2 est un bon compromis memoire/vitesse
        # Reduire a 1 si manque de memoire.
        per_device_train_batch_size=2,

        # Accumulation de gradient : simule un batch effectif de 2 x 4 = 8.
        # Un batch effectif plus grand stabilise l'entrainement.
        gradient_accumulation_steps=4,

        # Nombre de steps de warmup : augmente progressivement le learning rate
        # pendant les 5 premiers steps pour eviter une divergence au debut.
        warmup_steps=5,

        # Nombre d'epoques (passages complets sur le dataset).
        # Plus d'epoques permettent un meilleur apprentissage, mais prennent plus de temps.
        # Trop d'epoques peuvent causer de l'overfitting (le modele memorise les exemples au lieu d'apprendre).
        num_train_epochs=6,

        # Taux d'apprentissage. 2e-4 est le standard recommande par Unsloth
        # pour un fine-tuning efficace sur petit dataset.
        learning_rate=2e-4,

        # Frequence d'affichage des logs (loss) pendant l'entrainement.
        # 1 = affiche a chaque step pour bien suivre la convergence.
        logging_steps=1,

        # Optimiseur AdamW en 8 bits : economise de la VRAM tout en
        # gardant une bonne convergence.
        optim="adamw_8bit",

        # Regularisation L2 (weight decay) : penalise les poids trop grands.
        # 0.01 est plus fort que le 0.001 par defaut, pour limiter l'overfitting.
        weight_decay=0.01,

        # Scheduler cosine : le learning rate decroit en cosinus, ce qui est
        # generalement meilleur que "linear" pour les fine-tunings multi-epoques.
        lr_scheduler_type="cosine",

        # Graine aleatoire pour la reproductibilite.
        seed=3407,

        # Pas de reporting externe. Decommentez pour utiliser WandB :
        # report_to = "wandb",
        report_to="none",
    ),
)


# =============================================================================
# 6. MASQUAGE DES INSTRUCTIONS (TRAIN ON RESPONSES ONLY)
# =============================================================================
# Astuce cruciale : on calcule la loss UNIQUEMENT sur les reponses de
# l'assistant, pas sur les messages systeme ni les questions utilisateur.
# Cela force le modele a apprendre a GENERER de bonnes reponses
# au lieu de simplement memoriser les questions.

from unsloth.chat_templates import train_on_responses_only

trainer = train_on_responses_only(
    trainer,
    # Marqueur de debut d'une instruction (a ignorer dans la loss).
    instruction_part="<|im_start|>user\n",
    # Marqueur de debut d'une reponse (a inclure dans la loss).
    response_part="<|im_start|>assistant\n",
)

# Verification du masquage : on decode un exemple pour verifier
# que seule la reponse assistant est visible dans les labels.
print("\n--- Verification du masquage (seule la reponse doit apparaitre) ---")
sample_idx = min(5, len(trainer.train_dataset) - 1)
decoded_labels = tokenizer.decode(
    [tokenizer.pad_token_id if x == -100 else x for x in trainer.train_dataset[sample_idx]["labels"]]
).replace(tokenizer.pad_token, " ")
print(decoded_labels[:300])
print("...")


# =============================================================================
# 7. AFFICHAGE DES STATS MEMOIRE AVANT ENTRAINEMENT
# =============================================================================
gpu_stats = torch.cuda.get_device_properties(0)
start_gpu_memory = round(torch.cuda.max_memory_reserved() / 1024 / 1024 / 1024, 3)
max_memory = round(gpu_stats.total_memory / 1024 / 1024 / 1024, 3)
print(f"\nGPU = {gpu_stats.name}. Memoire max = {max_memory} Go.")
print(f"{start_gpu_memory} Go de memoire reservee avant entrainement.")


# =============================================================================
# 8. LANCEMENT DE L'ENTRAINEMENT
# =============================================================================
# C'est ici que le modele apprend !
# Surveillez la loss : elle doit diminuer progressivement.
# Explication: la loss est une mesure de l'erreur du modele. Au debut, la loss est elevee (ex: 2.0-3.0)
# car le modele ne connait pas encore les reponses. Au fur et a mesure de l'entrainement, 
# la loss doit diminuer (ex: 0.5-1.0) indiquant que le modele apprend a generer des reponses plus precises.

print("\n=== DEBUT DE L'ENTRAINEMENT ===\n")
trainer_stats = trainer.train()


# =============================================================================
# 9. STATS MEMOIRE APRES ENTRAINEMENT
# =============================================================================
used_memory = round(torch.cuda.max_memory_reserved() / 1024 / 1024 / 1024, 3)
used_memory_for_lora = round(used_memory - start_gpu_memory, 3)
used_percentage = round(used_memory / max_memory * 100, 3)
lora_percentage = round(used_memory_for_lora / max_memory * 100, 3)

print(f"\n=== ENTRAINEMENT TERMINE ===")
print(f"Duree : {trainer_stats.metrics['train_runtime']:.0f} secondes "
      f"({trainer_stats.metrics['train_runtime']/60:.1f} minutes)")
print(f"Memoire GPU pic = {used_memory} Go ({used_percentage}% du max)")
print(f"Memoire utilisee pour LoRA = {used_memory_for_lora} Go ({lora_percentage}%)")


# =============================================================================
# 10. TEST DU MODELE FINE-TUNE (INFERENCE)
# =============================================================================
# On teste le modele avec des questions typiques sur l'encaisseuse SP2322.
# Le modele devrait maintenant repondre avec des connaissances specifiques
# a la machine, en citant des references de pieces, des codes defaut, etc.

print("\n=== TEST DU MODELE ===\n")

# Liste de questions de test couvrant differentes categories
questions_test = [
    "Comment consigner correctement la machine avant intervention ?",
    "Pourquoi le bouton bleu REARMEMENT clignote ?",
    "Que faire si un robot ne prend plus le produit ?",
    "Quelles sont les frequences d'entretien des moteurs ?",
    "Comment diagnostiquer un defaut variateur M4 ?",
]

from transformers import TextStreamer

for i, question in enumerate(questions_test):
    print(f"\n{'='*60}")
    print(f"Question {i+1}: {question}")
    print(f"{'='*60}")

    messages = [
        # On inclut le prompt systeme pour guider le modele
        {
            "role": "system",
            "content": "Tu es un assistant technique expert de l'encaisseuse SP2322. "
                       "Tu reponds en francais de maniere precise et technique en te basant "
                       "sur la documentation officielle de la machine.",
        },
        {"role": "user", "content": question},
    ]

    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,  # Ajoute le prompt pour que le modele genere
    )

    _ = model.generate(
        **tokenizer(text, return_tensors="pt").to("cuda"),
        max_new_tokens=1024,              # Reponses techniques longues
        temperature=0.6, top_p=0.95, top_k=20,  # Parametres recommandes
        streamer=TextStreamer(tokenizer, skip_prompt=True),  # Affiche en streaming
    )
    print()

    # On ne teste qu'une question pour gagner du temps.
    # Commentez le break pour tester toutes les questions.
    # break


# =============================================================================
# 11. SAUVEGARDE DU MODELE
# =============================================================================

# --- 11a. Sauvegarde des adaptateurs LoRA (leger, ~100 Mo) ---
# Sauvegarde uniquement les poids LoRA. Pour utiliser le modele,
# il faudra recharger le modele de base + les adaptateurs.
LORA_OUTPUT_DIR = "sp2322_lora"
model.save_pretrained(LORA_OUTPUT_DIR)
tokenizer.save_pretrained(LORA_OUTPUT_DIR)
print(f"\nAdaptateurs LoRA sauvegardes dans : {LORA_OUTPUT_DIR}/")

# --- 11b. Export GGUF pour llama.cpp / Ollama (recommande pour la production) ---
#
# Decommentez UNE des lignes ci-dessous selon la quantification voulue :
# - q8_0 : meilleure qualite, ~4-5 Go (recommande si vous avez la memoire)
# - q4_k_m : bon compromis qualite/taille, ~2-3 Go (recommande pour production)
# - q6_k : entre les deux, ~3-4 Go

GGUF_OUTPUT_DIR = "sp2322_gguf"

# Export en Q4_K_M (recommande pour votre setup de production)
# NOTE: Cette étape nécessite 'make' et un compilateur C++ (gcc/clang) installés.
# Sur Windows sans environnement de compilation, cela échouera.
# Dans ce cas, utilisez le script de conversion manuel ou téléchargez les binaires llama.cpp.
try:
    model.save_pretrained_gguf(
        GGUF_OUTPUT_DIR,
        tokenizer,
        quantization_method="q4_k_m",
    )
    print(f"\nModele GGUF sauvegarde dans : {GGUF_OUTPUT_DIR}/")
except RuntimeError as e:
    print(f"\n[ATTENTION] La conversion automatique GGUF a echoue : {e}")
    print("Cependant, le modele fusionne (merged) a bien ete sauvegarde au format SafeTensors.")
    print(f"Vous pouvez le convertir manuellement en suivant ces instructions :")
    print(f"""
1. Clonez le repo llama.cpp : git clone https://github.com/ggml-org/llama.cpp
2. S'assurer d'être dans l'environnement virtuel `learner`: `.\.venv\Scripts\activate` (Windows) ou `source .venv/bin/activate` (Linux/Mac)
3. Convertir le modèle : `uv run llama.cpp/convert_hf_to_gguf.py sp2322_gguf/`
4. Le fichier GGUF converti se trouvera dans `sp2322_gguf/` avec un nom comme `Sp2322_Gguf-1.7B-BF16.gguf`.
5. Téléchargez les binaires de llama.cpp pour Windows pour quantification q4_k_m : https://github.com/ggml-org/llama.cpp/releases/
6. Quantifiez le modèle en q4_k_m : `.\llama-b8067-bin-win-cuda-13.1-x64\llama-quantize.exe sp2322_gguf\Sp2322_Gguf-1.7B-BF16.gguf sp2322_gguf\sp2322_q4_k_m.gguf q4_k_m`
7. Le modèle quantifié en q4_k_m se trouvera dans `sp2322_gguf/sp2322_q4_k_m.gguf`.
    """)

# Pour exporter en Q8_0 (meilleure qualite) :
# model.save_pretrained_gguf(GGUF_OUTPUT_DIR, tokenizer, quantization_method="q8_0")

# Pour exporter en 16 bits (pas de quantification, gros fichier) :
# model.save_pretrained_gguf(GGUF_OUTPUT_DIR, tokenizer, quantization_method="f16")

# =============================================================================
# 12. INSTRUCTIONS POST-ENTRAINEMENT
# =============================================================================
print(f"""
{'='*60}
  FINE-TUNING TERMINE AVEC SUCCES
{'='*60}

Fichiers generes :
  - {LORA_OUTPUT_DIR}/     : adaptateurs LoRA (pour reprendre l'entrainement)
  - {GGUF_OUTPUT_DIR}/     : modele GGUF (pour la production)

Pour utiliser le modele GGUF dans votre systeme RAG :
  1. Copiez le fichier .gguf dans semantic_search/data/models/
     (Le nom peut varier, ex: sp2322_gguf-unsloth.Q4_K_M.gguf)
  2. Modifiez le .env :
     LLM_MODEL_PATH=/app/models/VotreFichier.gguf
  3. Relancez : docker compose up -d api

Pour recharger les adaptateurs LoRA et continuer l'entrainement :
  model, tokenizer = FastLanguageModel.from_pretrained(
      model_name = "{LORA_OUTPUT_DIR}",
      max_seq_length = {MAX_SEQ_LENGTH},
      load_in_4bit = True,
  )
""")
