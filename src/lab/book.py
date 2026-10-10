import re
from dataclasses import dataclass

from lab.config import BOOK_PATH

START_MARKER = "*** START OF THE PROJECT GUTENBERG EBOOK"
END_MARKER = "*** END OF THE PROJECT GUTENBERG EBOOK"
SECOND_VOLUME_MARKER = "Segunda parte del ingenioso caballero don Quijote de la Mancha"
CHAPTER_PATTERN = re.compile(r"^\s*Cap[ií]tulo (primero|Primero|[IVXLC]+)\.\s*(.*)$")
SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?;:])\s+")
ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}

VOLUME_TITLES = {
    1: "El ingenioso hidalgo don Quijote de la Mancha (1605)",
    2: "Segunda parte del ingenioso caballero don Quijote de la Mancha (1615)",
}


@dataclass
class Chapter:
    volume: int
    number: int
    title: str
    paragraphs: list


def roman_to_int(roman):
    total = 0
    for current, following in zip(roman, roman[1:] + " "):
        value = ROMAN_VALUES[current]
        total += -value if ROMAN_VALUES.get(following, 0) > value else value
    return total


def _unwrap(lines):
    return " ".join(line.strip() for line in lines if line.strip())


def _paragraphs(lines):
    paragraphs, current = [], []
    for line in lines:
        if line.strip():
            current.append(line)
        elif current:
            paragraphs.append(_unwrap(current))
            current = []
    if current:
        paragraphs.append(_unwrap(current))
    return paragraphs


def chapters(path=BOOK_PATH):
    # Keeps only the chapters of the Project Gutenberg text (no license, prologues or poems).
    # The second volume starts when the chapter numbering goes back to 1.
    lines = path.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
    start = next(i for i, line in enumerate(lines) if line.startswith(START_MARKER))
    end = next(i for i, line in enumerate(lines) if line.startswith(END_MARKER))
    lines = lines[start + 1:end]

    headings, bodies, volume, reading, index = [], [], 1, False, 0
    while index < len(lines):
        match = CHAPTER_PATTERN.match(lines[index])
        if match:
            number = 1 if match.group(1).lower() == "primero" else roman_to_int(match.group(1))
            if headings and number <= headings[-1][1]:
                volume += 1
            # Chapter titles wrap over several lines until the first blank line
            title_lines = [match.group(2)]
            index += 1
            while index < len(lines) and lines[index].strip():
                title_lines.append(lines[index])
                index += 1
            headings.append((volume, number, _unwrap(title_lines)))
            bodies.append([])
            reading = True
            continue
        # The second volume's front matter (tasa, prólogo...) is not part of the last chapter of the first
        if lines[index].strip() == SECOND_VOLUME_MARKER:
            reading = False
        elif reading:
            bodies[-1].append(lines[index])
        index += 1
    return [Chapter(v, n, t, _paragraphs(body)) for (v, n, t), body in zip(headings, bodies)]


def _split_long_paragraph(paragraph, max_chars):
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


def chunk(paragraphs, max_chars=1200, overlap=1):
    # Packs whole paragraphs (or groups of sentences for very long ones) up to max_chars and repeats the last
    # `overlap` pieces at the start of the next chunk, so an idea cut at a boundary is complete in one of them.
    pieces = [piece for paragraph in paragraphs for piece in _split_long_paragraph(paragraph, max_chars)]
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


def documents(max_chars=1200):
    # One document per chunk; the _id (volume-chapter-position) is stable and readable
    return [{
        "_id": f"v{chapter.volume}-c{chapter.number:03d}-{position:03d}",
        "volume": chapter.volume,
        "volume_title": VOLUME_TITLES[chapter.volume],
        "chapter": chapter.number,
        "chapter_title": chapter.title,
        "position": position,
        "text": text,
    } for chapter in chapters() for position, text in enumerate(chunk(chapter.paragraphs, max_chars))]
