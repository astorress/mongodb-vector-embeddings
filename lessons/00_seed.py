# Lección 00 - Cargar el libro: la colección `chunks` de la base `quijote`, con un vector por documento.
#
#   1. Parseo: el texto de Project Gutenberg se convierte en 126 capítulos (2 volúmenes).
#   2. Chunking: cada capítulo se parte en fragmentos de ~1200 caracteres.
#   3. Embeddings: cada fragmento se convierte en un vector de 384 números con el modelo de embeddings.
#   4. insert_many: el texto, sus metadatos y su vector se guardan en el mismo documento.
#   5. Índices: uno normal en mongod y dos de búsqueda (vectorial y de texto completo) en mongot.
import time

from lab import book
from lab.client import get_client
from lab.config import EMBEDDING_MODEL, MONGO_DB, TEXT_INDEX, VECTOR_INDEX
from lab.embeddings import dimensions, embed_passages
from lab.search import create_search_indexes, wait_until_queryable
from lab.show import step, table, title

client = get_client()
db = client[MONGO_DB]

title("00 - Seed de la colección chunks")

step("Parseo y chunking del libro")
docs = book.documents()
lengths = [len(d["text"]) for d in docs]
print(f"{len({(d['volume'], d['chapter']) for d in docs})} capítulos -> {len(docs)} fragmentos "
      f"(entre {min(lengths)} y {max(lengths)} caracteres, promedio {sum(lengths) // len(lengths)})")

step(f"Embeddings con {EMBEDDING_MODEL}")
# Reuse the vectors of a previous seed when the text and the model are the same: calculating them is the slow part
previous = {(d["_id"], d["text"]): d["embedding"]
            for d in db.chunks.find({"model": EMBEDDING_MODEL}, {"text": 1, "embedding": 1})}
pending = [d for d in docs if (d["_id"], d["text"]) not in previous]
print(f"{len(docs) - len(pending)} vectores reutilizados del seed anterior, {len(pending)} por calcular")
started = time.monotonic()
for start in range(0, len(pending), 256):
    batch = pending[start:start + 256]
    for doc, vector in zip(batch, embed_passages([d["text"] for d in batch])):
        previous[(doc["_id"], doc["text"])] = vector
    print(f"  {start + len(batch)}/{len(pending)} ({time.monotonic() - started:.0f} s)")
for doc in docs:
    doc["embedding"] = previous[(doc["_id"], doc["text"])]
    doc["model"] = EMBEDDING_MODEL
print(f"Cada vector tiene {len(docs[0]['embedding'])} dimensiones")

step(f"Borrando la base '{MONGO_DB}' (si existe) y creando chunks")
client.drop_database(MONGO_DB)
result = db.chunks.insert_many(docs)
print("insertados:", len(result.inserted_ids))

step("Índice normal (B-tree, en mongod): {volume, chapter, position}")
db.chunks.create_index([("volume", 1), ("chapter", 1), ("position", 1)])

step("Índices de búsqueda (Lucene, en mongot): vectorial y de texto completo")
create_search_indexes(db.chunks, dimensions())
seconds = wait_until_queryable(db.chunks, [VECTOR_INDEX, TEXT_INDEX])
print(f"Listos en {seconds:.0f} s: mongot los construyó leyendo la colección por change streams")

step("Fragmentos por volumen")
table(db.chunks.aggregate([
    {"$group": {"_id": "$volume", "title": {"$first": "$volume_title"}, "chapters": {"$addToSet": "$chapter"},
                "chunks": {"$sum": 1}}},
    {"$sort": {"_id": 1}},
    {"$project": {"_id": 0, "volume": "$_id", "title": 1, "chapters": {"$size": "$chapters"}, "chunks": 1}},
]), ["volume", "title", "chapters", "chunks"])
print("\nSiguiente: python lessons/01_embeddings.py")
