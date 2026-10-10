import argparse
import textwrap

from rag import config
from rag.db import get_chunks
from rag.embeddings import embed_query

PROJECTION = {
    "_id": 1,
    "volume": 1,
    "chapter": 1,
    "chapter_title": 1,
    "position": 1,
    "text": 1,
}


def build_filter(volume=None, chapter=None):
    conditions = {}
    if volume is not None:
        conditions["volume"] = volume
    if chapter is not None:
        conditions["chapter"] = chapter
    return conditions


def vector_search_stage(query, k, volume=None, chapter=None, num_candidates=None):
    stage = {
        "index": config.VECTOR_INDEX,
        "path": "embedding",
        "queryVector": embed_query(query),
        # numCandidates = how many neighbours the HNSW graph explores; more = better recall, slower
        "numCandidates": num_candidates or k * 20,
        "limit": k,
    }
    filters = build_filter(volume, chapter)
    if filters:
        stage["filter"] = filters
    return {"$vectorSearch": stage}


def text_search_stage(query, volume=None, chapter=None):
    compound = {"must": [{"text": {"query": query, "path": ["text", "chapter_title"]}}]}
    filters = [{"equals": {"path": path, "value": value}} for path, value in build_filter(volume, chapter).items()]
    if filters:
        compound["filter"] = filters
    return {"$search": {"index": config.TEXT_INDEX, "compound": compound}}


def semantic_search(query, k=5, volume=None, chapter=None, num_candidates=None):
    pipeline = [
        vector_search_stage(query, k, volume, chapter, num_candidates),
        {"$project": {**PROJECTION, "score": {"$meta": "vectorSearchScore"}}},
    ]
    return list(get_chunks().aggregate(pipeline))


def text_search(query, k=5, volume=None, chapter=None):
    pipeline = [
        text_search_stage(query, volume, chapter),
        {"$limit": k},
        {"$project": {**PROJECTION, "score": {"$meta": "searchScore"}}},
    ]
    return list(get_chunks().aggregate(pipeline))


def hybrid_search(query, k=5, volume=None, chapter=None):
    # $rankFusion (MongoDB 8.1+) merges both rankings with Reciprocal Rank Fusion inside the server:
    # score = sum of 1 / (60 + rank) over the pipelines where the document appears
    candidates = k * 4
    pipeline = [
        {"$rankFusion": {"input": {"pipelines": {
            "semantic": [vector_search_stage(query, candidates, volume, chapter)],
            "text": [text_search_stage(query, volume, chapter), {"$limit": candidates}],
        }}}},
        {"$limit": k},
        {"$project": {**PROJECTION, "score": {"$meta": "score"}}},
    ]
    return list(get_chunks().aggregate(pipeline))


SEARCHES = {"semantic": semantic_search, "text": text_search, "hybrid": hybrid_search}


def search(query, mode="semantic", k=5, volume=None, chapter=None):
    return SEARCHES[mode](query, k=k, volume=volume, chapter=chapter)


def reference(document):
    return f"Vol. {document['volume']}, cap. {document['chapter']} (fragmento {document['position']})"


def print_results(results):
    for rank, document in enumerate(results, start=1):
        print(f"\n#{rank}  {reference(document)}  score={document['score']:.4f}")
        print(f"    {document['chapter_title']}")
        print(textwrap.indent(textwrap.fill(document["text"][:500] + "…", 100), "    | "))


def add_search_arguments(parser):
    parser.add_argument("query")
    parser.add_argument("--mode", choices=SEARCHES, default="semantic")
    parser.add_argument("-k", type=int, default=5, help="número de fragmentos a recuperar")
    parser.add_argument("--volume", type=int, choices=[1, 2], help="1 = 1605, 2 = 1615")
    parser.add_argument("--chapter", type=int)


def main():
    parser = argparse.ArgumentParser(description="Busca fragmentos de Don Quijote.")
    add_search_arguments(parser)
    args = parser.parse_args()
    print_results(search(args.query, args.mode, args.k, args.volume, args.chapter))


if __name__ == "__main__":
    main()
