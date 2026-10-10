import re
from dataclasses import dataclass

START_MARKER = "*** START OF THE PROJECT GUTENBERG EBOOK"
END_MARKER = "*** END OF THE PROJECT GUTENBERG EBOOK"
SECOND_VOLUME_MARKER = "Segunda parte del ingenioso caballero don Quijote de la Mancha"
CHAPTER_PATTERN = re.compile(r"^\s*Cap[ií]tulo (primero|Primero|[IVXLC]+)\.\s*(.*)$")

VOLUME_TITLES = {
    1: "El ingenioso hidalgo don Quijote de la Mancha (1605)",
    2: "Segunda parte del ingenioso caballero don Quijote de la Mancha (1615)",
}

ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}


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


def chapter_number(token):
    return 1 if token.lower() == "primero" else roman_to_int(token)


def unwrap(lines):
    return " ".join(line.strip() for line in lines if line.strip())


def split_paragraphs(lines):
    paragraphs, current = [], []
    for line in lines:
        if line.strip():
            current.append(line)
        elif current:
            paragraphs.append(unwrap(current))
            current = []
    if current:
        paragraphs.append(unwrap(current))
    return paragraphs


def body_lines(text):
    lines = text.replace("\r\n", "\n").split("\n")
    start = next(i for i, line in enumerate(lines) if line.startswith(START_MARKER))
    end = next(i for i, line in enumerate(lines) if line.startswith(END_MARKER))
    return lines[start + 1:end]


def parse_chapters(text):
    lines = body_lines(text)
    headings, bodies = [], []
    volume, reading = 1, False
    index = 0
    while index < len(lines):
        line = lines[index]
        match = CHAPTER_PATTERN.match(line)
        if match:
            number = chapter_number(match.group(1))
            if headings and number <= headings[-1][1]:
                volume += 1
            # Chapter titles wrap over several lines until the first blank line
            title_lines = [match.group(2)]
            index += 1
            while index < len(lines) and lines[index].strip():
                title_lines.append(lines[index])
                index += 1
            headings.append((volume, number, unwrap(title_lines)))
            bodies.append([])
            reading = True
            continue
        # The second volume's front matter (tasa, prólogo...) is not part of chapter LII
        if line.strip() == SECOND_VOLUME_MARKER:
            reading = False
        elif reading:
            bodies[-1].append(line)
        index += 1
    return [
        Chapter(volume, number, title, split_paragraphs(body))
        for (volume, number, title), body in zip(headings, bodies)
    ]


def load_chapters(path):
    return parse_chapters(path.read_text(encoding="utf-8"))
