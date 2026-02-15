from huggingface_hub import snapshot_download
import os

# Désactive les liens symboliques sur Windows pour éviter l'erreur de privilèges [WinError 1314]
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"

# On télécharge la version déjà quantifiée en 4-bit pour gagner du temps et de la RAM
model_id = "unsloth/qwen3-4b-instruct-2507-unsloth-bnb-4bit"
print(f"Début du téléchargement du modèle optimisé {model_id}...")
print("Cela peut prendre du temps (plusieurs Go). Des barres de progression devraient s'afficher.")

try:
    # On force l'affichage des barres de progression en s'assurant que le logger est actif
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # snapshot_download télécharge tout le repo dans le cache HuggingFace
    path = snapshot_download(
        repo_id=model_id,
        local_files_only=False, # On veut télécharger
        resume_download=True,   # Permet de reprendre si ça a coupé
    )
    print(f"\nModèle téléchargé avec succès dans : {path}")
    print("Vous pouvez maintenant lancer le script d'entraînement, il utilisera ces fichiers locaux.")
except Exception as e:
    print(f"\nErreur lors du téléchargement : {e}")
