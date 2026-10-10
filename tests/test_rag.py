from rag import config
from rag.book import load_chapters, roman_to_int
from rag.chunking import chunk_paragraphs


def test_roman_to_int():
    assert [roman_to_int(value) for value in ["I", "IV", "IX", "XL", "XLIX", "LII", "LXXIV"]] == [1, 4, 9, 40, 49, 52, 74]


def test_book_has_both_volumes():
    chapters = load_chapters(config.BOOK_PATH)
    volumes = [chapter.volume for chapter in chapters]
    assert volumes.count(1) == 52
    assert volumes.count(2) == 74
    assert chapters[0].title.startswith("Que trata de la condición y ejercicio del famoso hidalgo")
    assert "En un lugar de la Mancha" in chapters[0].paragraphs[0]
    assert all(chapter.paragraphs for chapter in chapters)


def test_second_volume_front_matter_is_not_in_last_chapter_of_first():
    last_of_first = [chapter for chapter in load_chapters(config.BOOK_PATH) if chapter.volume == 1][-1]
    assert not any("Hernando de Vallejo" in paragraph for paragraph in last_of_first.paragraphs)


def test_chunks_respect_size_and_overlap():
    paragraphs = [f"Párrafo {number}. " + "palabra " * 40 for number in range(20)]
    chunks = chunk_paragraphs(paragraphs, max_chars=800, overlap=1)
    assert all(len(chunk) <= 800 for chunk in chunks)
    assert chunks[1].split("\n")[0] == chunks[0].split("\n")[-1]


def test_long_paragraph_is_split_by_sentences():
    paragraph = " ".join(f"Frase número {number} que es bastante larga." for number in range(100))
    chunks = chunk_paragraphs([paragraph], max_chars=500, overlap=0)
    assert len(chunks) > 1
    assert all(len(chunk) <= 500 for chunk in chunks)

