import argparse
import time

from pymongo import ASCENDING, ReplaceOne

from rag import config
from rag.book import VOLUME_TITLES, load_chapters
from rag.chunking import chunk_paragraphs
from rag.db import get_chunks
from rag.embeddings import dimensions, embed_passages
from rag.indexes import ensure_indexes


def build_documents(chapters, max_chars):
    documents = []
    for chapter in chapters:
        for position, text in enumerate(chunk_paragraphs(chapter.paragraphs, max_chars=max_chars)):
            documents.append({
                "_id": f"v{chapter.volume}-c{chapter.number:03d}-{position:03d}",
                "volume": chapter.volume,
                "volume_title": VOLUME_TITLES[chapter.volume],
                "chapter": chapter.number,
                "chapter_title": chapter.title,
                "position": position,
                "text": text,
            })
    return documents


def main():
    parser = argparse.ArgumentParser(description="Carga Don Quijote en MongoDB con sus embeddings.")
    parser.add_argument("--reset", action="store_true", help="borra la colección antes de cargar")
    parser.add_argument("--max-chars", type=int, default=1200, help="tamaño máximo de cada fragmento")
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args()

    collection = get_chunks()
    if args.reset:
        collection.drop()
        print(f"Colección {config.CHUNKS_COLLECTION} borrada")

    chapters = load_chapters(config.BOOK_PATH)
    documents = build_documents(chapters, args.max_chars)
    print(f"{len(chapters)} capítulos -> {len(documents)} fragmentos")

    # Only embed what is missing, so an interrupted load resumes where it stopped
    loaded = set(collection.distinct("_id", {"embedding": {"$exists": True}}))
    pending = [document for document in documents if document["_id"] not in loaded]
    print(f"{len(loaded)} ya cargados, {len(pending)} por cargar (modelo {config.EMBEDDING_MODEL})")

    started = time.monotonic()
    for start in range(0, len(pending), args.batch_size):
        batch = pending[start:start + args.batch_size]
        vectors = embed_passages([document["text"] for document in batch])
        operations = [
            ReplaceOne({"_id": document["_id"]}, {**document, "embedding": vector}, upsert=True)
            for document, vector in zip(batch, vectors)
        ]
        collection.bulk_write(operations, ordered=False)
        done = start + len(batch)
        print(f"  {done}/{len(pending)} fragmentos ({time.monotonic() - started:.0f}s)")

    collection.create_index([("volume", ASCENDING), ("chapter", ASCENDING), ("position", ASCENDING)])
    print("Índices de búsqueda (mongot):")
    ensure_indexes(collection, dimensions())
    print(f"Listo: {collection.count_documents({})} fragmentos en {config.MONGODB_DATABASE}.{config.CHUNKS_COLLECTION}")


if __name__ == "__main__":
    main()
