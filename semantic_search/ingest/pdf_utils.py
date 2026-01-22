
from pathlib import Path
import fitz  # PyMuPDF
import re
from typing import Iterator, Tuple, List

def extract_pages(pdf_path: Path) -> Iterator[Tuple[int, str]]:
    doc = fitz.open(pdf_path)
    for i, page in enumerate(doc):
        text = page.get_text("text")
        yield i+1, text or ""
    doc.close()

def split_into_sentences(text: str) -> List[str]:
    """
    Découpe le texte en phrases en utilisant des patterns regex.
    Gère les abréviations courantes et les cas limites.
    """
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
    # Normalisation des espaces
    text = " ".join(text.split())

    if len(text) <= size:
        yield text
        return

    # Découper en phrases
    sentences = split_into_sentences(text)

    if not sentences:
        # Fallback sur le chunking basique si pas de phrases détectées
        start = 0
        while start < len(text):
            end = min(start + size, len(text))
            yield text[start:end]
            if end == len(text):
                break
            start = end - overlap
        return

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
                word_len = len(word) + 1  # +1 pour l'espace
                if temp_length + word_len > size and temp_chunk:
                    yield " ".join(temp_chunk)
                    # Garder quelques mots pour l'overlap
                    overlap_words = int(len(temp_chunk) * (overlap / size))
                    temp_chunk = temp_chunk[-overlap_words:] if overlap_words > 0 else []
                    temp_length = sum(len(w) + 1 for w in temp_chunk)

                temp_chunk.append(word)
                temp_length += word_len

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
