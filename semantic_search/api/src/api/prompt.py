"""RAG prompt construction for LLM generation."""
from typing import List, Dict, Tuple

from llm.base import ChatMessage

SYSTEM_PROMPT = """Tu es un assistant documentaire intelligent. Tu réponds aux questions en te basant UNIQUEMENT sur les extraits de documents fournis ci-dessous.

Règles :
- Réponds en français.
- Cite tes sources avec le format [Source : titre, page X].
- Si les extraits ne contiennent pas assez d'information pour répondre, dis-le clairement.
- Sois concis et précis.
- Ne fabrique jamais d'information qui ne figure pas dans les extraits."""


def build_rag_prompt(
    query: str,
    chunks: List[Tuple[Dict, float]],
    conversation_history: List[ChatMessage] | None = None,
    max_history: int = 5,
) -> List[ChatMessage]:
    """Build a list of ChatMessages for the LLM including context and history.

    Args:
        query: The user's current question.
        chunks: List of (doc_dict, score) tuples from search.
        conversation_history: Previous messages in the conversation.
        max_history: Max number of user/assistant exchange pairs to keep.

    Returns:
        Ordered list of ChatMessage ready for the LLM.
    """
    messages: List[ChatMessage] = [ChatMessage(role="system", content=SYSTEM_PROMPT)]

    # Add conversation history (sliding window)
    if conversation_history:
        # Keep last max_history pairs (user+assistant = 2 messages each)
        recent = conversation_history[-(max_history * 2):]
        messages.extend(recent)

    # Build context block from retrieved chunks
    context_parts: List[str] = []
    for i, (doc, score) in enumerate(chunks, start=1):
        title = doc.get("title", "Document")
        page = doc.get("page", "?")
        source_type = doc.get("source_type", "")
        content = doc.get("content", "")
        score_pct = round(score * 100, 1)
        context_parts.append(
            f"[Extrait {i}] (source: {title}, page {page}, type: {source_type}, pertinence: {score_pct}%)\n{content}"
        )

    context_block = "\n\n---\n\n".join(context_parts)

    user_content = f"""Voici les extraits de documents pertinents :

{context_block}

---

Question : {query}"""

    messages.append(ChatMessage(role="user", content=user_content))
    return messages
