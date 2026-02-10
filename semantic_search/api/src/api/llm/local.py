import os
import asyncio
import logging
import queue
import threading
from pathlib import Path
from typing import AsyncIterator, Dict, Any, List, Optional

from .base import LLMService, ChatMessage, LLMConfig

# Configuration du logger pour ce module. Le logger est utilisé pour enregistrer des messages d'information, d'avertissement et d'erreur liés au service de langage local.
logger = logging.getLogger(__name__)

class LocalLLMService(LLMService):
    """ Implémentation locale du service de langage (LLM) utilisant le modèle LLaMA via la bibliothèque llama-cpp-python. """

    def __init__(self, model_path: str = "", config: Optional[LLMConfig] = None):
        """ 
        Initialise le service de langage local. 
        - model_path: chemin vers le modèle à utiliser (par exemple, un chemin local vers un modèle LLaMA).
        - config: une instance de LLMConfig pour configurer le service. Si None, les valeurs par défaut seront utilisées (en se basant sur les variables d'environnement ou les valeurs par défaut codées en dur).
        """
        self._model = None
        self._model_path = model_path
        # Un verrou pour synchroniser l'accès au modèle lors de la génération de texte, afin d'éviter les problèmes de concurrence.
        self._lock = asyncio.Lock()

        # Si aucune configuration n'est fournie, on crée une configuration par défaut en se basant sur les variables d'environnement ou les valeurs par défaut codées en dur.
        if config is None:
            from ..config import (
                LLM_N_CTX, LLM_N_THREADS, LLM_GPU_LAYERS,
                LLM_TEMPERATURE, LLM_MAX_TOKENS
            )
            self._config = LLMConfig(
                model_path=model_path,
                n_ctx=LLM_N_CTX,
                n_threads=LLM_N_THREADS if LLM_N_THREADS > 0 else (os.cpu_count() or 4) // 2,
                n_gpu_layers=LLM_GPU_LAYERS,
                temperature=LLM_TEMPERATURE,
                max_tokens=LLM_MAX_TOKENS,
            )
        else:
            self._config = config

        # Charger le modèle.
        self._load_model()

    def _load_model(self):
        # Si le chemin du modèle n'est pas défini ou si le fichier n'existe pas, on considère que le service de langage n'est pas disponible.
        # Un message d'avertissement est enregistré dans les logs.
        if not self._model_path or not Path(self._model_path).is_file():
            if self._model_path:
                logger.warning(f"Fichier de modèle LLM non trouvé: {self._model_path}")
            else:
                logger.info("LLM_MODEL_PATH non défini, les fonctionnalités LLM sont désactivées")
            return

        # Tenter de charger le modèle en utilisant la bibliothèque llama-cpp-python.
        # Si la bibliothèque n'est pas installée ou si le chargement échoue, des messages d'erreur sont enregistrés dans les logs.
        try:
            # Import local pour éviter d'avoir une dépendance obligatoire sur llama-cpp-python si le service de langage n'est pas utilisé.
            from llama_cpp import Llama
            logger.info(f"Chargement du modèle LLM depuis {self._model_path}...")
            # Le modèle est chargé avec les paramètres spécifiés dans la configuration (n_ctx, n_threads, n_gpu_layers).
            self._model = Llama(
                model_path=self._model_path,
                n_ctx=self._config.n_ctx,
                n_threads=self._config.n_threads,
                n_gpu_layers=self._config.n_gpu_layers,
                verbose=False,
            )
            logger.info("Modèle LLM chargé avec succès")
        except ImportError:
            logger.warning("llama-cpp-python n'est pas installé, les fonctionnalités LLM sont désactivées")
        except Exception as e:
            logger.error(f"Impossible de charger le modèle LLM : {e}")

    def is_available(self) -> bool:
        """Indique si le service de langage est disponible (par exemple, si le modèle est chargé correctement)."""
        return self._model is not None

    async def generate(self, messages: List[ChatMessage]) -> str:
        """Génère une réponse basée sur une liste de messages de chat."""
        if not self.is_available():
            raise RuntimeError("Le modèle LLM n'est pas disponible")

        # Formater les messages de chat dans le format attendu par la bibliothèque llama-cpp-python (une liste de dictionnaires avec les clés "role" et "content").
        formatted = [{"role": m.role, "content": m.content} for m in messages]

        # Utiliser un verrou pour synchroniser l'accès au modèle lors de la génération de texte, afin d'éviter les problèmes de concurrence.
        # La génération est effectuée dans un thread séparé pour ne pas bloquer la boucle d'événements asyncio.
        async with self._lock:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._sync_generate, formatted)
        return result

    def _sync_generate(self, messages: List[dict]) -> str:
        """Méthode de génération synchrone qui sera exécutée dans un thread séparé."""
        # Appeler la méthode create_chat_completion du modèle pour générer une réponse basée sur les messages formatés, en utilisant les paramètres de température et de max_tokens spécifiés dans la configuration.
        response = self._model.create_chat_completion(
            messages=messages,
            temperature=self._config.temperature,
            max_tokens=self._config.max_tokens,
        )
        # La réponse générée est extraite du résultat retourné par la méthode create_chat_completion.
        # On accède au contenu de la première (et généralement unique) réponse générée.
        return response["choices"][0]["message"]["content"]

    async def generate_stream(self, messages: List[ChatMessage]) -> AsyncIterator[str]:
        """
        Génère une réponse en streaming basée sur une liste de messages de chat.
        Permet de recevoir la réponse token par token au fur et à mesure de sa génération, ce qui peut améliorer la réactivité de l'interface utilisateur.
        """

        if not self.is_available():
            raise RuntimeError("LLM model not available")

        # Formater les messages de chat dans le format attendu par la bibliothèque llama-cpp-python (une liste de dictionnaires avec les clés "role" et "content").
        formatted = [{"role": m.role, "content": m.content} for m in messages]
        # Création d'une queue pour communiquer entre le thread de génération et la boucle d'événements asyncio. Les tokens générés seront placés dans cette queue.
        token_queue: queue.Queue = queue.Queue()
        # Un holder pour stocker une éventuelle exception qui pourrait survenir dans le thread de génération, afin de pouvoir la propager correctement dans la boucle d'événements asyncio.
        error_holder: List[Optional[Exception]] = [None]

        def _run_generation():
            """
            Fonction qui sera exécutée dans un thread séparé pour générer la réponse en streaming.
            Les tokens générés sont placés dans la queue, et les exceptions sont capturées dans le holder d'erreur.
            """

            # try-except pour capturer les exceptions qui pourraient survenir lors de la génération, afin de les propager correctement dans la boucle d'événements asyncio.
            try:
                # La méthode create_chat_completion est appelée avec le paramètre stream=True pour générer la réponse en streaming.
                # Les tokens générés sont extraits du résultat et placés dans la queue à mesure qu'ils sont produits.
                for chunk in self._model.create_chat_completion(
                    messages=formatted,
                    temperature=self._config.temperature,
                    max_tokens=self._config.max_tokens,
                    stream=True,
                ):
                    # Extraire le token généré du chunk retourné par la méthode create_chat_completion.
                    # Le token est généralement contenu dans la clé "delta" du chunk, sous la clé "content".
                    delta = chunk["choices"][0].get("delta", {})
                    content = delta.get("content", "")
                    # Si un token a été généré (c'est-à-dire si le champ "content" n'est pas vide), on le place dans la queue pour qu'il puisse être consommé par la boucle d'événements asyncio.
                    if content:
                        token_queue.put(content)
                token_queue.put(None)  # Signaler la fin de la génération en plaçant un token None dans la queue.
            except Exception as e:
                error_holder[0] = e
                token_queue.put(None)

        # Utiliser un verrou pour synchroniser l'accès au modèle lors de la génération de texte, afin d'éviter les problèmes de concurrence.
        async with self._lock:
            # Lancer la fonction de génération dans un thread séparé pour ne pas bloquer la boucle d'événements asyncio.
            thread = threading.Thread(target=_run_generation, daemon=True)
            thread.start()

            while True:
                # Attendre qu'un token soit disponible dans la queue.
                # Si la queue est vide, on attend un court instant avant de vérifier à nouveau pour éviter de bloquer la boucle d'événements asyncio.
                while True:
                    try:
                        token = token_queue.get_nowait()
                        break
                    except queue.Empty:
                        await asyncio.sleep(0.01)

                # Si le token est None, cela signifie que la génération est terminée.
                # Avant de sortir de la boucle, on vérifie s'il y a eu une exception dans le thread de génération et on la lève si nécessaire.
                if token is None:
                    if error_holder[0]:
                        raise error_holder[0]
                    break

                # Si un token a été généré, on le yield pour qu'il puisse être consommé par la boucle d'événements asyncio.
                yield token

    def get_model_info(self) -> Dict[str, Any]:
        """Retourne des informations sur le modèle utilisé (par exemple, nom, version, etc.)."""
        return {
            "backend": "llama-cpp-python",
            "model_path": self._model_path,
            "available": self.is_available(),
            "n_ctx": self._config.n_ctx,
            "n_threads": self._config.n_threads,
            "n_gpu_layers": self._config.n_gpu_layers,
        }
