"""Construction des prompts RAG pour la génération par le LLM."""

from typing import List, Dict, Tuple, Literal

from .llm.base import ChatMessage

ResponseMode = Literal["rag", "knowledge", "hybrid"]

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


KNOWLEDGE_SYSTEM_PROMPT = """Tu es un assistant intelligent et compétent qui répond aux questions en français.

Instructions principales :
1. Réponds EN FRANÇAIS de manière claire et précise.
2. Utilise tes connaissances générales pour fournir une réponse informative et utile.
3. Sois conversationnel et pédagogique dans tes explications.
4. Si tu n'es pas certain d'une information, indique-le clairement.
5. Structure tes réponses de manière logique avec des exemples si pertinent.
6. N'invente pas de faits. Si tu ne sais pas, dis-le honnêtement.

Important : tu n'as pas accès à des documents spécifiques pour cette question, donc base ta réponse sur tes connaissances générales."""


HYBRID_SYSTEM_PROMPT = """Tu es un assistant intelligent spécialisé qui combine des documents spécifiques avec des connaissances générales.

Instructions principales :
1. Réponds EN FRANÇAIS uniquement.
2. Tu as accès à des extraits de documents, MAIS ils semblent peu pertinents pour la question posée.
3. Commence par mentionner brièvement ce que disent les documents (si pertinent), puis enrichis ta réponse avec tes connaissances générales.
4. Cite les sources des documents quand tu les utilises : [Source : titre du document, page X]
5. Indique clairement quand tu passes de l'information documentaire aux connaissances générales.
6. Sois conversationnel mais précis. Privilégie la clarté et l'utilité pour l'utilisateur.

Format suggéré :
- Si les documents contiennent quelque chose d'utile : mentionne-le en citant la source
- Puis : "Pour compléter cette information..." ou "De manière plus générale..."
- Fournis une réponse complète basée sur tes connaissances

Important : l'objectif est d'être utile à l'utilisateur, même si les documents disponibles ne couvrent pas entièrement sa question."""


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
        recent = conversation_history[-(max_history * 2) :]
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


def build_knowledge_prompt(
    query: str,
    conversation_history: List[ChatMessage] | None = None,
    max_history: int = 5,
) -> List[ChatMessage]:
    """Construit un prompt pour le mode 'knowledge' (sans documents RAG).

    Ce mode est utilisé quand aucun document pertinent n'est trouvé. Le LLM répond
    alors avec ses connaissances générales sans s'appuyer sur des documents spécifiques.

    Args:
        query: La question actuelle de l'utilisateur.
        conversation_history: Messages précédents de la conversation.
        max_history: Nombre maximum de paires d'échanges à conserver.

    Returns:
        Liste ordonnée de ChatMessage prête pour le LLM.
    """
    messages: List[ChatMessage] = [
        ChatMessage(role="system", content=KNOWLEDGE_SYSTEM_PROMPT)
    ]

    # Ajouter l'historique de conversation
    if conversation_history:
        recent = conversation_history[-(max_history * 2) :]
        messages.extend(recent)

    # Question simple sans contexte documentaire
    messages.append(ChatMessage(role="user", content=query))
    return messages


def build_hybrid_prompt(
    query: str,
    chunks: List[Tuple[Dict, float]],
    conversation_history: List[ChatMessage] | None = None,
    max_history: int = 5,
) -> List[ChatMessage]:
    """Construit un prompt pour le mode 'hybrid' (documents peu pertinents + connaissances).

    Ce mode est utilisé quand des documents sont trouvés mais leur pertinence est faible.
    Le LLM peut les mentionner brièvement mais doit surtout s'appuyer sur ses connaissances.

    Args:
        query: La question actuelle de l'utilisateur.
        chunks: Liste de tuples (doc_dict, score) avec faible pertinence.
        conversation_history: Messages précédents de la conversation.
        max_history: Nombre maximum de paires d'échanges à conserver.

    Returns:
        Liste ordonnée de ChatMessage prête pour le LLM.
    """
    messages: List[ChatMessage] = [
        ChatMessage(role="system", content=HYBRID_SYSTEM_PROMPT)
    ]

    # Ajouter l'historique de conversation
    if conversation_history:
        recent = conversation_history[-(max_history * 2) :]
        messages.extend(recent)

    # Construire un contexte minimal avec les documents
    context_parts: List[str] = []
    for i, (doc, score) in enumerate(chunks, start=1):
        title = doc.get("title", "Document")
        page = doc.get("page", "?")
        content = doc.get("content", "")
        score_pct = round(score * 100, 1)
        context_parts.append(
            f"[Extrait {i}] (source: {title}, page {page}, pertinence: {score_pct}%)\n{content[:300]}..."
        )

    context_block = "\n\n---\n\n".join(context_parts)

    user_content = f"""J'ai trouvé ces extraits de documents, mais ils semblent peu pertinents pour ta question :

{context_block}

---

Question : {query}

Note : Ces documents ne semblent pas couvrir complètement ta question. N'hésite pas à compléter avec tes connaissances générales."""

    messages.append(ChatMessage(role="user", content=user_content))
    return messages


def determine_response_mode(
    results: List[Tuple[Dict, float]],
    relevance_threshold: float = 0.3,
    min_results: int = 1,
) -> ResponseMode:
    """Détermine le mode de réponse approprié basé sur la pertinence des résultats.

    Args:
        results: Liste de tuples (doc_dict, score) provenant de la recherche.
        relevance_threshold: Seuil de pertinence pour considérer un résultat comme bon.
        min_results: Nombre minimum de résultats pertinents requis.

    Returns:
        "rag" si les résultats sont pertinents (mode standard)
        "knowledge" si aucun résultat pertinent (utilise les connaissances du LLM)
        "hybrid" si résultats moyennement pertinents (documents + connaissances)
    """
    if not results:
        return "knowledge"

    # Compter les résultats au-dessus du seuil de pertinence
    relevant_results = [score for _, score in results if score >= relevance_threshold]

    if len(relevant_results) >= min_results:
        # Assez de résultats pertinents → mode RAG standard
        return "rag"
    elif len(results) > 0 and results[0][1] >= (relevance_threshold * 0.5):
        # Quelques résultats mais pas assez pertinents → mode hybride
        return "hybrid"
    else:
        # Aucun résultat pertinent → mode knowledge pur
        return "knowledge"


def build_prompt_by_mode(
    mode: ResponseMode,
    query: str,
    chunks: List[Tuple[Dict, float]],
    conversation_history: List[ChatMessage] | None = None,
    max_history: int = 5,
) -> List[ChatMessage]:
    """Construit le prompt approprié selon le mode de réponse.

    Args:
        mode: Mode de réponse ("rag", "knowledge", ou "hybrid")
        query: La question actuelle de l'utilisateur.
        chunks: Liste de tuples (doc_dict, score) provenant de la recherche.
        conversation_history: Messages précédents de la conversation.
        max_history: Nombre maximum de paires d'échanges à conserver.

    Returns:
        Liste ordonnée de ChatMessage prête pour le LLM.
    """
    if mode == "rag":
        return build_rag_prompt(query, chunks, conversation_history, max_history)
    elif mode == "knowledge":
        return build_knowledge_prompt(query, conversation_history, max_history)
    else:  # hybrid
        return build_hybrid_prompt(query, chunks, conversation_history, max_history)
