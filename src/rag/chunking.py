import re

SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?;:])\s+")


def split_long_paragraph(paragraph, max_chars):
    if len(paragraph) <= max_chars:
        return [paragraph]
    pieces, current = [], ""
    for sentence in SENTENCE_BOUNDARY.split(paragraph):
        if current and len(current) + len(sentence) + 1 > max_chars:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        pieces.append(current)
    return pieces


def chunk_paragraphs(paragraphs, max_chars=1200, overlap=1):
    # Packs whole paragraphs (or sentence groups for very long ones) up to max_chars and repeats
    # the last `overlap` pieces at the start of the next chunk, so an idea cut at a boundary
    # still appears complete in at least one chunk.
    pieces = [piece for paragraph in paragraphs for piece in split_long_paragraph(paragraph, max_chars)]
    chunks, current = [], []
    for piece in pieces:
        if current and sum(len(p) + 1 for p in current) + len(piece) > max_chars:
            chunks.append("\n".join(current))
            current = current[-overlap:] if overlap else []
            if sum(len(p) + 1 for p in current) + len(piece) > max_chars:
                current = []
        current.append(piece)
    if current:
        chunks.append("\n".join(current))
    return chunks
