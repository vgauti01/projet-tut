import re
from typing import Iterator, List


def clean_pdf_artifacts(text: str) -> str:
    """
    Nettoie les artefacts courants des PDFs (lignes de points, caractères parasites, etc.).
    NE PAS appliquer sur du texte markdown provenant de Docling.
    """
    if not text:
        return text

    # 1. Supprime les lignes de points de table des matières
    text = re.sub(r'\.{5,}', ' ', text)
    text = re.sub(r'\s+\.{3,}\s+\d+\s*$', ' ', text, flags=re.MULTILINE)

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
    """Découpe le texte en phrases en utilisant des patterns regex."""
    if not text.strip():
        return []

    sentence_endings = r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<![A-Z]\.)(?<=\.|\?|\!)\s+'
    sentences = re.split(sentence_endings, text)
    return [s.strip() for s in sentences if s.strip()]


def _is_table_line(line: str) -> bool:
    """Détecte si une ligne fait partie d'un tableau markdown."""
    stripped = line.strip()
    return stripped.startswith('|') and stripped.endswith('|')


def _split_markdown_sections(text: str) -> List[str]:
    """
    Découpe le texte markdown en sections logiques.
    Respecte : headers, tableaux, paragraphes.
    """
    lines = text.split('\n')
    sections: List[str] = []
    current_section: List[str] = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # Début d'un header markdown → nouvelle section
        if re.match(r'^#{1,6}\s', line) and current_section:
            sections.append('\n'.join(current_section))
            current_section = [line]
            i += 1
            continue

        # Début d'un tableau markdown → garder le tableau entier ensemble
        if _is_table_line(line):
            table_lines = []
            while i < len(lines) and _is_table_line(lines[i]):
                table_lines.append(lines[i])
                i += 1
            current_section.append('\n'.join(table_lines))
            continue

        # Paragraphe vide → séparateur de section si la section est assez grande
        if not line.strip() and current_section:
            current_section.append(line)
            i += 1
            continue

        current_section.append(line)
        i += 1

    if current_section:
        sections.append('\n'.join(current_section))

    return [s for s in sections if s.strip()]


def chunk_text(text: str, size: int = 800, overlap: int = 200) -> Iterator[str]:
    """
    Découpe le texte en chunks intelligents qui respectent la structure markdown.

    Stratégie :
    1. Découpe par sections markdown (headers)
    2. Si une section est trop grande, découpe par paragraphes
    3. Si un paragraphe est trop grand, découpe par phrases
    4. Ne coupe jamais un tableau markdown en deux

    Args:
        text: Le texte à découper (peut être du markdown)
        size: Taille cible du chunk (en caractères)
        overlap: Overlap entre les chunks pour préserver le contexte

    Yields:
        Des chunks de texte qui respectent la structure markdown
    """
    if not text or not text.strip():
        return

    # Texte court → un seul chunk, pas besoin de découper
    if len(text) <= size:
        yield text.strip()
        return

    # Découpe en sections markdown
    sections = _split_markdown_sections(text)

    current_chunk: List[str] = []
    current_length = 0

    for section in sections:
        section_length = len(section)

        # Section qui tient dans un chunk → l'ajouter directement
        if section_length <= size:
            # Si ajouter cette section dépasse la taille, yield le chunk actuel
            if current_length + section_length > size and current_chunk:
                yield '\n\n'.join(current_chunk).strip()

                # Overlap : garder les dernières sections qui tiennent dans l'overlap
                overlap_sections: List[str] = []
                overlap_length = 0
                for s in reversed(current_chunk):
                    if overlap_length + len(s) <= overlap:
                        overlap_sections.insert(0, s)
                        overlap_length += len(s)
                    else:
                        break
                current_chunk = overlap_sections
                current_length = overlap_length

            current_chunk.append(section)
            current_length += section_length
            continue

        # Section trop grande → la découper par paragraphes/phrases
        # D'abord yield le chunk en cours
        if current_chunk:
            yield '\n\n'.join(current_chunk).strip()
            current_chunk = []
            current_length = 0

        # Découper la section en morceaux
        yield from _chunk_large_section(section, size, overlap)

    # Yield le dernier chunk
    if current_chunk:
        yield '\n\n'.join(current_chunk).strip()


def _chunk_large_section(text: str, size: int, overlap: int) -> Iterator[str]:
    """Découpe une section trop grande en chunks par paragraphes puis par phrases."""
    # Séparer par doubles sauts de ligne (paragraphes)
    paragraphs = re.split(r'\n\n+', text)

    current_chunk: List[str] = []
    current_length = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        para_length = len(para)

        # Paragraphe qui tient dans un chunk
        if para_length <= size:
            if current_length + para_length > size and current_chunk:
                yield '\n\n'.join(current_chunk).strip()

                # Overlap
                overlap_parts: List[str] = []
                ol = 0
                for p in reversed(current_chunk):
                    if ol + len(p) <= overlap:
                        overlap_parts.insert(0, p)
                        ol += len(p)
                    else:
                        break
                current_chunk = overlap_parts
                current_length = ol

            current_chunk.append(para)
            current_length += para_length
            continue

        # Paragraphe trop grand → découper par phrases
        if current_chunk:
            yield '\n\n'.join(current_chunk).strip()
            current_chunk = []
            current_length = 0

        # Si c'est un tableau, le garder entier même s'il dépasse
        if _is_table_line(para.split('\n')[0]):
            yield para.strip()
            continue

        # Sinon, découper par phrases
        yield from _chunk_by_sentences(para, size, overlap)

    if current_chunk:
        yield '\n\n'.join(current_chunk).strip()


def _chunk_by_sentences(text: str, size: int, overlap: int) -> Iterator[str]:
    """Découpe un texte trop long par phrases (fallback final)."""
    sentences = split_into_sentences(text)
    if not sentences:
        yield text.strip()
        return

    current_chunk: List[str] = []
    current_length = 0

    for sentence in sentences:
        sent_len = len(sentence)

        # Phrase seule trop longue → la couper par caractères
        if sent_len > size * 1.5:
            if current_chunk:
                yield ' '.join(current_chunk)
                current_chunk = []
                current_length = 0

            start = 0
            while start < sent_len:
                end = min(start + size, sent_len)
                yield sentence[start:end]
                if end >= sent_len:
                    break
                start = end - overlap
            continue

        if current_length + sent_len > size and current_chunk:
            yield ' '.join(current_chunk)

            # Overlap par phrases
            overlap_sents: List[str] = []
            ol = 0
            for s in reversed(current_chunk):
                if ol + len(s) <= overlap:
                    overlap_sents.insert(0, s)
                    ol += len(s)
                else:
                    break
            current_chunk = overlap_sents
            current_length = ol

        current_chunk.append(sentence)
        current_length += sent_len + 1

    if current_chunk:
        yield ' '.join(current_chunk)
