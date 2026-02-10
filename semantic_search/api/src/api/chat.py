"""Chat endpoints with session management and SSE streaming."""
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

from config import TOP_K, RRF_K, LLM_MAX_HISTORY
from search import (
    embed_model, cross_encoder, search_meilisearch, search_qdrant, sigmoid
)
from utils import reciprocal_rank_fusion, extract_terms, format_answer
from metrics import SearchMetrics, ModelMetrics
from llm import get_llm_service
from llm.base import ChatMessage
from prompt import build_rag_prompt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])

# ── In-memory session store ──────────────────────────────────────────────

class ChatSession:
    def __init__(self, conversation_id: str):
        self.conversation_id = conversation_id
        self.messages: List[Dict[str, str]] = []
        self.created_at = datetime.utcnow().isoformat()
        self.updated_at = self.created_at

    def add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})
        self.updated_at = datetime.utcnow().isoformat()

    def get_history_as_chat_messages(self) -> List[ChatMessage]:
        return [ChatMessage(role=m["role"], content=m["content"]) for m in self.messages]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "messages": self.messages,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


_sessions: Dict[str, ChatSession] = {}

# ── Request / Response models ────────────────────────────────────────────

class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    conversation_id: Optional[str] = None
    limit: Optional[int] = Field(None, ge=1, le=100)

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("La requête ne peut pas être vide")
        return v


# ── Endpoints ────────────────────────────────────────────────────────────

@router.post("/new")
async def new_conversation():
    cid = str(uuid.uuid4())
    _sessions[cid] = ChatSession(cid)
    return {"conversation_id": cid}


@router.get("/{conversation_id}")
async def get_conversation(conversation_id: str):
    session = _sessions.get(conversation_id)
    if not session:
        raise HTTPException(status_code=404, detail="Conversation non trouvée")
    return session.to_dict()


@router.post("")
async def chat(req: ChatRequest):
    q = req.query
    limit = req.limit or TOP_K

    # Resolve or create session
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
    with SearchMetrics(q) as search_metrics:
        meili_start = time.time()
        meili_task = asyncio.create_task(search_meilisearch(q, limit))
        qdrant_start = time.time()
        qdrant_task = asyncio.create_task(search_qdrant(q, limit))

        meili_hits, vector_hits = await asyncio.gather(meili_task, qdrant_task)
        search_metrics.record_stage("meili", time.time() - meili_start)
        search_metrics.record_stage("qdrant", time.time() - qdrant_start)

        if not meili_hits and not vector_hits:
            logger.error("Both search engines failed")
            raise HTTPException(status_code=503, detail="Les moteurs de recherche sont indisponibles.")

        if not meili_hits:
            search_mode = "qdrant_only"
        elif not vector_hits:
            search_mode = "meili_only"
        else:
            search_mode = "hybrid"
        search_metrics.set_mode(search_mode)

        # RRF fusion
        rrf_start = time.time()
        candidates = reciprocal_rank_fusion(meili_hits, vector_hits, k=RRF_K, limit=50)
        search_metrics.record_stage("rrf", time.time() - rrf_start)

        # Cross-encoder reranking
        rerank_inputs = []
        docs_map = {}
        for i, (doc, _) in enumerate(candidates):
            docs_map[i] = doc
            rerank_inputs.append((q, doc.get("content", "")))

        final_results = []
        if rerank_inputs:
            try:
                rerank_start = time.time()
                with ModelMetrics("rerank"):
                    scores = cross_encoder.predict(rerank_inputs)
                search_metrics.record_stage("rerank", time.time() - rerank_start)

                ranked = []
                for i, score in enumerate(scores):
                    ranked.append((docs_map[i], float(sigmoid(score))))
                ranked.sort(key=lambda x: x[1], reverse=True)
                final_results = ranked[:limit]
            except Exception as e:
                logger.error(f"Re-ranking failed: {e}. Falling back to RRF.")
                final_results = candidates[:limit]
        search_metrics.set_results_count(len(final_results))

    # ── LLM generation or fallback ──
    llm = get_llm_service()

    if not llm.is_available():
        # Fallback: return search results without LLM
        terms = extract_terms(q)
        answer = format_answer(q, final_results, terms)
        answer["conversation_id"] = session.conversation_id
        answer["llm_available"] = False
        session.add_message("assistant", answer.get("answer", ""))
        return answer

    # Build sources metadata for SSE
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

    # Build prompt
    history = session.get_history_as_chat_messages()
    # Exclude the last user message (we'll include it in the RAG prompt)
    history_for_prompt = history[:-1] if history else []
    prompt_messages = build_rag_prompt(q, final_results, history_for_prompt, LLM_MAX_HISTORY)

    # SSE streaming response
    async def event_stream():
        full_response = ""
        try:
            # Meta event
            yield f"event: meta\ndata: {json.dumps({'conversation_id': session.conversation_id})}\n\n"

            # Sources event
            yield f"event: sources\ndata: {json.dumps(sources_data, ensure_ascii=False)}\n\n"

            # Token events
            async for token in llm.generate_stream(prompt_messages):
                full_response += token
                yield f"event: token\ndata: {json.dumps({'content': token}, ensure_ascii=False)}\n\n"

            # Done event
            yield f"event: done\ndata: {json.dumps({'full_response': full_response}, ensure_ascii=False)}\n\n"

            # Save assistant response
            session.add_message("assistant", full_response)

        except Exception as e:
            logger.error(f"SSE streaming error: {e}")
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
            if full_response:
                session.add_message("assistant", full_response)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
