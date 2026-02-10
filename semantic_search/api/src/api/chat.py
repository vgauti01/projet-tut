"""Points de terminaison du chat avec gestion de session et streaming SSE."""
import asyncio
import json
import logging
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from .config import TOP_K, LLM_MAX_HISTORY
from .search import (
    perform_hybrid_search
)
from .utils import extract_terms, format_answer
from .metrics import ModelMetrics
from .llm import get_llm_service
from .llm.base import ChatMessage
from .prompt import build_rag_prompt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])

# ── Stockage des sessions en mémoire ─────────────────────────────────────

class ChatSession:
    """
    Représente une session de chat avec un historique de messages.
    Chaque session est identifiée par un conversation_id unique, et stocke les messages échangés entre l'utilisateur et l'assistant,
    ainsi que les timestamps de création et de mise à jour pour permettre la gestion de l'historique et des contextes de conversation.
    """
    def __init__(self, conversation_id: str):
        """Initialise une nouvelle session de chat avec un ID de conversation unique."""
        self.conversation_id = conversation_id
        self.messages: List[Dict[str, str]] = []
        self.created_at = datetime.utcnow().isoformat()
        self.updated_at = self.created_at

    def add_message(self, role: str, content: str):
        """Ajoute un message à l'historique de la session."""
        self.messages.append({"role": role, "content": content})
        self.updated_at = datetime.utcnow().isoformat()

    def get_history_as_chat_messages(self) -> List[ChatMessage]:
        """Retourne l'historique sous forme d'objets ChatMessage pour le LLM."""
        return [ChatMessage(role=m["role"], content=m["content"]) for m in self.messages]

    def to_dict(self) -> Dict[str, Any]:
        """Convertit la session en dictionnaire pour les réponses API."""
        return {
            "conversation_id": self.conversation_id,
            "messages": self.messages,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

# Les sessions de chat sont stockées dans un dictionnaire en mémoire, avec le conversation_id comme clé.
_sessions: Dict[str, ChatSession] = {}

# ── Modèles de Requête / Réponse ─────────────────────────────────────────

class ChatRequest(BaseModel):
    """
    Modèle de requête pour le point de terminaison de chat.
    Ce modèle valide que la requête contient une chaîne de caractères non vide pour la question (query),
    et que la limite de résultats (limit) est un entier positif entre 1 et 100 si elle est fournie.
    """
    query: str = Field(..., min_length=1, max_length=1000)
    conversation_id: Optional[str] = None
    limit: Optional[int] = Field(None, ge=1, le=100)

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("La requête ne peut pas être vide ou composée uniquement d'espaces")
        return v


# ── Points de Terminaison (Endpoints) ────────────────────────────────────

@router.post("/new")
async def new_conversation():
    """Crée une nouvelle identité de conversation unique."""
    cid = str(uuid.uuid4())
    _sessions[cid] = ChatSession(cid)
    return {"conversation_id": cid}


@router.get("/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Récupère l'historique complet d'une conversation."""
    session = _sessions.get(conversation_id)
    if not session:
        raise HTTPException(status_code=404, detail="Conversation non trouvée")
    return session.to_dict()


@router.post("")
async def chat(req: ChatRequest):
    """Gère une requête de chat asynchrone avec streaming de réponse."""
    q = req.query
    limit = req.limit or TOP_K

    # Résoudre ou créer une session
    if req.conversation_id:
        session = _sessions.get(req.conversation_id)
        if not session:
            raise HTTPException(status_code=404, detail="Conversation non trouvée")
    else:
        cid = str(uuid.uuid4())
        session = ChatSession(cid)
        _sessions[cid] = session

    # Record user message
    session.add_message("user", q)

    # ── Hybrid retrieval ──
    # Permet d'exécuter la recherche hybride mutualisée et de récupérer les résultats finaux ainsi que le mode de recherche utilisé (vectoriel, lexical, ou combiné).
    final_results, search_mode = await perform_hybrid_search(q, limit)

    # Si les deux moteurs de recherche ont échoué, on retourne une erreur 503 pour indiquer que le service est temporairement indisponible.
    if search_mode == "failed":
        logger.error("Moteurs de recherche indisponibles, impossibilité de traiter la requête.")
        raise HTTPException(status_code=503, detail="Les moteurs de recherche sont indisponibles.")

    # ── Génération LLM ou repli ──
    llm = get_llm_service()

    if not llm.is_available():
        # Si le LLM n'est pas disponible, on retourne une réponse formatée avec les résultats de la recherche sans génération de texte, et on enregistre que le LLM n'était pas disponible dans la session.
        logger.warning("Le LLM n'est pas disponible, retour de la réponse sans génération de texte.")
        terms = extract_terms(q)
        answer = format_answer(q, final_results, terms)
        answer["conversation_id"] = session.conversation_id
        answer["llm_available"] = False
        session.add_message("assistant", answer.get("answer", ""))
        return answer

    # Préparer les données des sources pour l'événement SSE, en extrayant les informations pertinentes de chaque document retourné par la recherche hybride,
    # telles que le titre, la page, le chemin, le score de pertinence, le type de source et un aperçu du contenu.
    sources_data = []
    for doc, score in final_results:
        sources_data.append({
            "title": doc.get("title", "Document"),
            "page": doc.get("page", "?"),
            "path": doc.get("path", ""),
            "score": round(score, 4),
            "source_type": doc.get("source_type", ""),
            "content_preview": (doc.get("content", ""))[:200],
        })

    # Construire le prompt
    history = session.get_history_as_chat_messages()
    # Exclure le dernier message de l'utilisateur (nous l'inclurons dans le prompt RAG)
    history_for_prompt = history[:-1] if history else []
    # Construire le prompt RAG en combinant le système, l'historique de la conversation (sauf le dernier message), et les extraits de documents pertinents pour fournir un contexte riche au LLM lors de la génération de la réponse.
    prompt_messages = build_rag_prompt(q, final_results, history_for_prompt, LLM_MAX_HISTORY)

    # SSE streaming response
    async def event_stream():
        """
        Génère une réponse en streaming via Server-Sent Events (SSE) en envoyant des événements pour
        les métadonnées, les sources, les tokens générés, et la réponse finale complète.
        """
        # Réponse complète en construction pour être enregistrée dans la session à la fin du streaming.
        full_response = ""
        try:
            # Événement méta: envoie l'ID de conversation pour que le client puisse associer les événements à la bonne session de chat.
            yield f"event: meta\ndata: {json.dumps({'conversation_id': session.conversation_id})}\n\n"

            # Événement sources: envoie les données des sources extraites de la recherche hybride pour que le client puisse les afficher pendant que le LLM génère la réponse.
            yield f"event: sources\ndata: {json.dumps(sources_data, ensure_ascii=False)}\n\n"

            # Événements tokens: envoie chaque token généré par le LLM au fur et à mesure de sa génération pour permettre un affichage en temps réel de la réponse, tout en construisant la réponse complète pour l'enregistrer à la fin.
            async for token in llm.generate_stream(prompt_messages):
                full_response += token
                yield f"event: token\ndata: {json.dumps({'content': token}, ensure_ascii=False)}\n\n"

            # Événement done: une fois que la génération est terminée, envoie la réponse complète finale pour que le client puisse l'afficher et l'enregistrer dans la session.
            yield f"event: done\ndata: {json.dumps({'full_response': full_response}, ensure_ascii=False)}\n\n"

            # Enregistrer la réponse de l'assistant
            session.add_message("assistant", full_response)

        except Exception as e:
            # En cas d'erreur pendant le streaming, on envoie un événement d'erreur avec les détails de l'exception, et on s'assure que la session est mise à jour avec une indication que la génération a échoué.
            logger.error(f"Erreur lors du streaming de la réponse: {e}")
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
            if full_response:
                session.add_message("assistant", full_response)

    # Retourne une réponse de streaming SSE avec les événements générés par la fonction event_stream, en définissant les en-têtes appropriés pour le streaming et en s'assurant que le client peut traiter les événements correctement.
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
