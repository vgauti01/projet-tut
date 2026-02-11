import re
from typing import Iterator, List


def clean_pdf_artifacts(text: str) -> str:
    """
    Nettoie les artefacts courants des PDFs (lignes de points, caractères parasites, etc.).

    Args:
        text: Texte brut extrait du PDF

    Returns:
        Texte nettoyé
    """
    if not text:
        return text

    # 1. Supprime les lignes de points de table des matières (ex: "Introduction ........ 7")
    # Pattern: au moins 5 points consécutifs (pour éviter de supprimer "..." normal)
    # OU 3+ points suivis d'un nombre (numéro de page)
    text = re.sub(r'\.{5,}', ' ', text)  # 5+ points consécutifs
    text = re.sub(r'\s+\.{3,}\s+\d+\s*$', ' ', text, flags=re.MULTILINE)  # ... suivi de numéro de page en fin de ligne

    # 2. Supprime les longues séquences de tirets ou underscores
    text = re.sub(r'[-_]{3,}', '', text)

    # 3. Supprime les lignes vides multiples
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)

    # 4. Normalise les espaces multiples (mais garde les sauts de ligne)
    text = re.sub(r'[ \t]+', ' ', text)

    # 5. Supprime les espaces en début/fin de lignes
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines)

    return text.strip()


def split_into_sentences(text: str) -> List[str]:
    """
    Découpe le texte en phrases en utilisant des patterns regex.
    Gère les abréviations courantes et les cas limites.
    """
    if not text.strip():
        return []

    # Patterns pour détecter les fins de phrases
    # Gère: M., Dr., etc., i.e., e.g., et autres abréviations courantes
    sentence_endings = r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<![A-Z]\.)(?<=\.|\?|\!)\s+'
    sentences = re.split(sentence_endings, text)
    return [s.strip() for s in sentences if s.strip()]

def chunk_text(text: str, size: int = 1200, overlap: int = 150) -> Iterator[str]:
    """
    Découpe le texte en chunks intelligents qui respectent les limites de phrases.

    Args:
        text: Le texte à découper
        size: Taille cible du chunk (en caractères)
        overlap: Overlap entre les chunks pour préserver le contexte

    Yields:
        Des chunks de texte qui respectent les limites de phrases
    """
    if not text:
        return

    # Normalisation des espaces
    text = " ".join(text.split())

    if len(text) <= size:
        yield text
        return

    # Découper en phrases
    sentences = split_into_sentences(text)

    # Note: sentences ne sera jamais vide ici car text a été vérifié au début
    # et split_into_sentences renvoie au moins [text] s'il ne trouve pas de ponctuation.

    current_chunk = []
    current_length = 0

    i = 0
    while i < len(sentences):
        sentence = sentences[i]
        sentence_length = len(sentence)

        # Si une phrase seule dépasse la taille, la découper
        if sentence_length > size * 1.5:
            # Yield le chunk actuel si non vide
            if current_chunk:
                yield " ".join(current_chunk)
                current_chunk = []
                current_length = 0

            # Découper la phrase longue en sous-parties
            words = sentence.split()
            temp_chunk = []
            temp_length = 0

            for word in words:
                word_len = len(word)
                
                # Si le mot seul dépasse la taille, on doit le couper par caractères
                if word_len > size:
                    # On vide d'abord ce qu'il y a dans temp_chunk
                    if temp_chunk:
                        yield " ".join(temp_chunk)
                        temp_chunk = []
                        temp_length = 0
                    
                    # On débite le mot géant par morceaux
                    start = 0
                    while start < word_len:
                        end = min(start + size, word_len)
                        yield word[start:end]
                        if end == word_len:
                            break
                        start = end - overlap
                    continue

                if temp_length + word_len + 1 > size and temp_chunk:
                    yield " ".join(temp_chunk)
                    # Garder quelques mots pour l'overlap
                    overlap_words = int(len(temp_chunk) * (overlap / size))
                    temp_chunk = temp_chunk[-overlap_words:] if overlap_words > 0 else []
                    temp_length = sum(len(w) + 1 for w in temp_chunk)

                temp_chunk.append(word)
                temp_length += word_len + 1

            if temp_chunk:
                yield " ".join(temp_chunk)

            i += 1
            continue

        # Si ajouter cette phrase dépasse la taille
        if current_length + sentence_length > size and current_chunk:
            # Yield le chunk actuel
            yield " ".join(current_chunk)

            # Créer l'overlap: garder les dernières phrases qui rentrent dans l'overlap
            overlap_chunk = []
            overlap_length = 0

            for s in reversed(current_chunk):
                s_len = len(s)
                if overlap_length + s_len <= overlap:
                    overlap_chunk.insert(0, s)
                    overlap_length += s_len
                else:
                    break

            current_chunk = overlap_chunk
            current_length = overlap_length

        # Ajouter la phrase au chunk actuel
        current_chunk.append(sentence)
        current_length += sentence_length + 1  # +1 pour l'espace
        i += 1

    # Yield le dernier chunk s'il existe
    if current_chunk:
        yield " ".join(current_chunk)
