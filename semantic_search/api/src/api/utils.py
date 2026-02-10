
from typing import List, Dict, Tuple
import re
from collections import defaultdict

def highlight(text: str, terms: List[str]) -> str:
    """
    Surligne les termes pertinents dans le texte.
    """
    if not terms:
        return text
    # Trier par longueur décroissante pour éviter les conflits de highlighting
    sorted_terms = sorted(terms, key=len, reverse=True)
    pattern = r"\b(" + "|".join(map(re.escape, sorted_terms)) + r")\b"
    return re.sub(pattern, r"**\1**", text, flags=re.IGNORECASE)

def reciprocal_rank_fusion(
    meili_hits: List[Dict],
    vector_hits: List[Dict],
    k: int = 60,
    limit: int = 10
) -> List[Tuple[Dict, float]]:
    """
    Fusionne les résultats de Meilisearch et Qdrant en utilisant Reciprocal Rank Fusion.

    RRF Score = sum(1 / (k + rank_i)) pour chaque système

    Args:
        meili_hits: Résultats de Meilisearch (BM25)
        vector_hits: Résultats de Qdrant (Vector)
        k: Constante pour éviter les divisions par zéro (généralement 60)
        rank_i: Rang du document dans le système i (1-based)
        limit: Nombre de résultats à retourner

    Returns:
        Liste de tuples (document, score) triée par score décroissant
    """
    scores = defaultdict(float)
    doc_map = {}

    # Scorer les résultats de Meilisearch
    for rank, hit in enumerate(meili_hits, start=1):
        doc_id = hit.get("id")
        if doc_id:
            scores[doc_id] += 1.0 / (k + rank)
            if doc_id not in doc_map:
                doc_map[doc_id] = hit

    # Scorer les résultats de Qdrant
    for rank, hit in enumerate(vector_hits, start=1):
        doc_id = hit.get("id")
        if doc_id:
            scores[doc_id] += 1.0 / (k + rank)
            if doc_id not in doc_map:
                doc_map[doc_id] = hit

    # Trier par score décroissant
    sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    # Retourner les top résultats avec leurs scores
    return [(doc_map[doc_id], score) for doc_id, score in sorted_results[:limit]]

def format_answer(query: str, hits: List[Tuple[Dict, float]], terms: List[str]) -> Dict:
    """
    Assemble une réponse structurée à partir des extraits avec scores.

    Args:
        query: La question de l'utilisateur
        hits: Liste de tuples (document, score)
        terms: Termes à surligner

    Returns:
        Dictionnaire contenant la réponse formatée
    """
    excerpts = []
    unique_sources = []
    seen_sources = set()

    for doc, score in hits:
        content = doc.get("_formatted", {}).get("content", doc.get("content", ""))
        content = highlight(content, terms)

        source_info = {
            "title": doc.get("title", "Document"),
            "page": doc.get("page", "?"),
            "path": doc.get("path", "unknown"),
            "score": round(score, 4),
            "source_type": doc.get("source_type", "pdf"),
        }

        excerpts.append({
            "content": content,
            "source": source_info,
            "relevance_score": round(score * 100, 1)  # Score en pourcentage pour l'UI
        })

        src_str = f"{source_info['path']} (p. {source_info['page']})"
        if src_str not in seen_sources:
            unique_sources.append(src_str)
            seen_sources.add(src_str)

    return {
        "answer": "Voici les informations trouvées dans vos documents :",
        "excerpts": excerpts,
        "sources": unique_sources,
        "total_results": len(excerpts)
    }

def extract_terms(q: str) -> List[str]:
    """
    Extrait les termes significatifs d'une requête pour le highlighting.

    Args:
        q: La requête

    Returns:
        Liste de termes pertinents
    """
    # Extraire les mots, nombres et termes avec tirets
    terms = re.findall(r"[A-Za-zÀ-ÿ0-9\-]+", q)

    # Filtrer les stop words courants et les termes trop courts
    stop_words = {
        "le", "la", "les", "un", "une", "des", "du", "de", "et", "ou", "mais",
        "pour", "dans", "sur", "avec", "sans", "comment", "quoi", "qui", "que",
        "quel", "quelle", "quels", "quelles", "est", "sont", "a", "ont", "the",
        "and", "or", "but", "for", "in", "on", "at", "to", "of", "is", "are"
    }

    # Les termes significatifs sont ceux qui ont plus de 2 caractères et ne sont pas des stop words.
    significant_terms = [
        t for t in terms
        if len(t) > 2 and t.lower() not in stop_words
    ]

    return significant_terms
