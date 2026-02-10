"""Construction des prompts RAG pour la génération par le LLM."""
from typing import List, Dict, Tuple

from .llm.base import ChatMessage

# Prompt système qui définit le rôle de l'assistant et les règles de réponse pour le LLM.
# Ce prompt est utilisé pour guider le comportement du LLM lors de la génération des réponses basées sur les extraits de documents fournis.
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
    """Construit une liste de ChatMessages pour le LLM incluant le contexte et l'historique.

    Args:
        query: La question actuelle de l'utilisateur.
        chunks: Liste de tuples (doc_dict, score) provenant de la recherche.
        conversation_history: Messages précédents de la conversation.
        max_history: Nombre maximum de paires d'échanges (utilisateur/assistant) à conserver.

    Returns:
        Liste ordonnée de ChatMessage prête pour le LLM.
    """
    messages: List[ChatMessage] = [ChatMessage(role="system", content=SYSTEM_PROMPT)]

    # S'il y a un historique de conversation, on conserve les derniers échanges jusqu'à la limite définie par max_history pour fournir un contexte supplémentaire au LLM, tout en évitant de surcharger le prompt avec trop d'informations historiques.
    if conversation_history:
        recent = conversation_history[-(max_history * 2):]
        messages.extend(recent)

    # On construit le contexte à partir des extraits de documents pertinents.
    # Chaque extrait est formaté pour inclure le titre, la page, le type de source, et la pertinence (score) pour aider le LLM à comprendre l'importance relative de chaque extrait.
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
