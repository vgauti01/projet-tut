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

from .config import TOP_K, LLM_MAX_HISTORY, RAG_RELEVANCE_THRESHOLD, RAG_MIN_RESULTS
from .search import perform_hybrid_search
from .utils import extract_terms, format_answer
from .metrics import track_request_metrics, ChatMetrics, ERROR_COUNT
from .llm import get_llm_service
from .llm.base import ChatMessage
from .prompt import build_prompt_by_mode, determine_response_mode

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
        return [
            ChatMessage(role=m["role"], content=m["content"]) for m in self.messages
        ]

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
            raise ValueError(
                "La requête ne peut pas être vide ou composée uniquement d'espaces"
            )
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
@track_request_metrics("/chat")
async def chat(req: ChatRequest):
    """Gère une requête de chat asynchrone avec streaming de réponse."""
    chat_metrics = ChatMetrics()
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
    search_start = time.time()
    final_results, search_mode, timings = await perform_hybrid_search(q, limit)
    chat_metrics.record_search_duration(time.time() - search_start)

    # Si les deux moteurs de recherche ont échoué, on retourne une erreur 503.
    if search_mode == "failed":
        logger.error(
            "Moteurs de recherche indisponibles, impossibilité de traiter la requête."
        )
        ERROR_COUNT.labels(error_type="SearchUnavailable", endpoint="/chat").inc()
        raise HTTPException(
            status_code=503, detail="Les moteurs de recherche sont indisponibles."
        )

    # ── Génération LLM ou repli ──
    llm = get_llm_service()

    if not llm.is_available():
        logger.warning(
            "Le LLM n'est pas disponible, retour de la réponse sans génération de texte."
        )
        chat_metrics.set_path("fallback")
        terms = extract_terms(q)
        answer = format_answer(q, final_results, terms)
        answer["conversation_id"] = session.conversation_id
        answer["llm_available"] = False
        answer["search_mode"] = search_mode
        answer["timings"] = timings
        session.add_message("assistant", answer.get("answer", ""))
        chat_metrics.finish()
        return answer

    # Préparer les données des sources pour l'événement SSE, en extrayant les informations pertinentes de chaque document retourné par la recherche hybride,
    # telles que le titre, la page, le chemin, le score de pertinence, le type de source et un aperçu du contenu.
    sources_data = []
    for doc, score in final_results:
        sources_data.append(
            {
                "title": doc.get("title", "Document"),
                "page": doc.get("page", "?"),
                "path": doc.get("path", ""),
                "score": round(score, 4),
                "source_type": doc.get("source_type", ""),
                "content_preview": (doc.get("content", ""))[:200],
            }
        )

    # Déterminer le mode de réponse basé sur la pertinence des résultats
    response_mode = determine_response_mode(
        final_results, RAG_RELEVANCE_THRESHOLD, RAG_MIN_RESULTS
    )
    logger.info(f"Mode de réponse sélectionné : {response_mode}")

    # Construire le prompt
    history = session.get_history_as_chat_messages()
    # Exclure le dernier message de l'utilisateur (nous l'inclurons dans le prompt)
    history_for_prompt = history[:-1] if history else []
    # Construire le prompt approprié selon le mode (RAG, knowledge, ou hybrid)
    prompt_messages = build_prompt_by_mode(
        response_mode, q, final_results, history_for_prompt, LLM_MAX_HISTORY
    )

    # SSE streaming response
    chat_metrics.set_path("llm")

    async def event_stream():
        """
        Génère une réponse en streaming via Server-Sent Events (SSE) en envoyant des événements pour
        les métadonnées, les sources, les tokens générés, et la réponse finale complète.
        """
        full_response = ""
        llm_start = None
        ttft = None
        chat_metrics.start_generation()
        try:
            yield f"event: meta\ndata: {json.dumps({'conversation_id': session.conversation_id})}\n\n"

            yield f"event: sources\ndata: {json.dumps(sources_data, ensure_ascii=False)}\n\n"

            yield f"event: timings\ndata: {json.dumps({'search_mode': search_mode, 'response_mode': response_mode, 'timings': timings}, ensure_ascii=False)}\n\n"

            llm_start = time.time()
            async for token in llm.generate_stream(prompt_messages):
                if ttft is None:
                    ttft = round((time.time() - llm_start) * 1000, 1)
                chat_metrics.record_first_token()
                chat_metrics.record_token()
                full_response += token
                yield f"event: token\ndata: {json.dumps({'content': token}, ensure_ascii=False)}\n\n"

            llm_total = round((time.time() - llm_start) * 1000, 1) if llm_start else 0
            done_data = {
                "full_response": full_response,
                "llm_ttft_ms": ttft or 0,
                "llm_total_ms": llm_total,
            }
            yield f"event: done\ndata: {json.dumps(done_data, ensure_ascii=False)}\n\n"

            session.add_message("assistant", full_response)

        except Exception as e:
            logger.error(f"Erreur lors du streaming de la réponse: {e}")
            ERROR_COUNT.labels(error_type=type(e).__name__, endpoint="/chat").inc()
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
            if full_response:
                session.add_message("assistant", full_response)
        finally:
            chat_metrics.finish_generation()
            chat_metrics.finish()

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
