import os
from pathlib import Path

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27027/?directConnection=true")
MONGO_DB = os.getenv("MONGO_DB", "quijote")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")

BOOK_PATH = Path(__file__).resolve().parents[2] / "data" / "don_quijote.txt"

VECTOR_INDEX = "chunks_vector_index"
TEXT_INDEX = "chunks_text_index"

CLAUDE_MODEL = "claude-opus-5-5"
