import os
from pathlib import Path

MONGODB_URI = os.environ["MONGODB_URI"]
MONGODB_DATABASE = os.environ.get("MONGODB_DATABASE", "quijote")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")

BOOK_PATH = Path(__file__).resolve().parents[2] / "data" / "don_quijote.txt"

CHUNKS_COLLECTION = "chunks"
VECTOR_INDEX = "chunks_vector_index"
TEXT_INDEX = "chunks_text_index"

CLAUDE_MODEL = "claude-opus-5-5"
