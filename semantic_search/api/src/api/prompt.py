"""Construction des prompts RAG pour la génération par le LLM."""
from typing import List, Dict, Tuple

from .llm.base import ChatMessage

# Prompt système qui définit le rôle de l'assistant et les règles de réponse pour le LLM.
# Ce prompt est utilisé pour guider le comportement du LLM lors de la génération des réponses basées sur les extraits de documents fournis.
SYSTEM_PROMPT = """Tu es un assistant documentaire spécialisé. Tu aides les utilisateurs à comprendre leurs documents en français.

Instructions principales :
1. Réponds EN FRANÇAIS uniquement, sans traduire les termes techniques ou noms propres du document (ex: "API", "FastAPI", "Qdrant").
2. Base ta réponse UNIQUEMENT sur les extraits fournis. N'invente RIEN et n'ajoute pas d'informations qui ne sont pas dans les extraits.
3. Utilise PRIORITAIREMENT les extraits avec les scores de pertinence les plus élevés (>70%). Ignore ou mentionne avec prudence les extraits avec des scores faibles (<50%).
4. Cite TOUJOURS tes sources : [Source : titre du document, page X] pour chaque information tirée d'un extrait.
5. Si un extrait est incomplet, ambigu, ou peu pertinent par rapport à la question, dis-le explicitement et ne force pas son utilisation.
6. Si plusieurs documents se contredisent, signale-le clairement.
7. Sois conversationnel mais précis. Privilégie la clarté sur la concision.

Gestion des cas limites :
- Extraits peu pertinents (score <50%) → "Cet extrait semble peu pertinent pour ta question..."
- Documents qui se contredisent → "Les documents X et Y divergent sur ce point : ..."
- Question hors des documents → "Je n'ai pas trouvé d'information pertinente sur ce sujet dans les documents fournis."
- Synthèse cross-documents → Regroupe par thème et cite chaque source avec son score de pertinence.
- Terme ambigu/jargon → Explique brièvement en contexte si l'extrait le permet.

Important : reste prudent et honnête. Si tu doutes, cite l'extrait exact et son score plutôt que d'interpréter."""


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
