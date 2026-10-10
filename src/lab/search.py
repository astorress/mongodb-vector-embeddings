import textwrap
import time

from pymongo.operations import SearchIndexModel

from lab.config import TEXT_INDEX, VECTOR_INDEX
from lab.embeddings import embed_query

FIELDS = {"_id": 1, "volume": 1, "chapter": 1, "chapter_title": 1, "position": 1, "text": 1}


# ---------------------------------------------------------------- search indexes (built and kept by mongot)
def vector_index(dimensions):
    return {"fields": [
        {"type": "vector", "path": "embedding", "numDimensions": dimensions, "similarity": "cosine"},
        # filter fields can be used in $vectorSearch.filter (pre-filtering before the ANN search)
        {"type": "filter", "path": "volume"},
        {"type": "filter", "path": "chapter"},
    ]}


TEXT_INDEX_DEFINITION = {"mappings": {"dynamic": False, "fields": {
    "text": {"type": "string", "analyzer": "lucene.spanish"},
    "chapter_title": {"type": "string", "analyzer": "lucene.spanish"},
    "volume": {"type": "number"},
    "chapter": {"type": "number"},
}}}


def search_indexes(collection):
    return {index["name"]: index for index in collection.list_search_indexes()}


def create_search_indexes(collection, dimensions):
    collection.create_search_indexes([
        SearchIndexModel(definition=vector_index(dimensions), name=VECTOR_INDEX, type="vectorSearch"),
        SearchIndexModel(definition=TEXT_INDEX_DEFINITION, name=TEXT_INDEX, type="search"),
    ])


def wait_until_queryable(collection, names, timeout=600):
    # mongot builds the indexes asynchronously from the change stream: PENDING -> BUILDING -> READY
    started = time.monotonic()
    while time.monotonic() - started < timeout:
        indexes = search_indexes(collection)
        pending = [name for name in names if not indexes.get(name, {}).get("queryable")]
        if not pending:
            return time.monotonic() - started
        print(f"  {time.monotonic() - started:4.0f}s  " +
              ", ".join(f"{name}={indexes.get(name, {}).get('status')}" for name in pending))
        time.sleep(3)
    raise TimeoutError(f"Search indexes not queryable after {timeout}s: {names}")


# ---------------------------------------------------------------- query stages
def vector_stage(query, k=5, filter=None, num_candidates=None, exact=False):
    stage = {"index": VECTOR_INDEX, "path": "embedding", "limit": k,
             "queryVector": query if isinstance(query, list) else embed_query(query)}
    if exact:
        stage["exact"] = True
    else:
        # how many neighbours the HNSW graph explores before keeping the best `limit`: more = better recall
        stage["numCandidates"] = num_candidates or k * 20
    if filter:
        stage["filter"] = filter
    return {"$vectorSearch": stage}


def text_stage(query, filter=None):
    compound = {"must": [{"text": {"query": query, "path": ["text", "chapter_title"]}}]}
    if filter:
        compound["filter"] = [{"equals": {"path": path, "value": value}} for path, value in filter.items()]
    return {"$search": {"index": TEXT_INDEX, "compound": compound}}


# ---------------------------------------------------------------- the three kinds of search
def semantic(collection, query, k=5, filter=None):
    return list(collection.aggregate([
        vector_stage(query, k, filter),
        {"$project": {**FIELDS, "score": {"$meta": "vectorSearchScore"}}},
    ]))


def full_text(collection, query, k=5, filter=None):
    return list(collection.aggregate([
        text_stage(query, filter),
        {"$limit": k},
        {"$project": {**FIELDS, "score": {"$meta": "searchScore"}}},
    ]))


def hybrid(collection, query, k=5, filter=None):
    # $rankFusion (MongoDB 8.1+) merges both rankings with Reciprocal Rank Fusion inside the server:
    # score = sum of 1 / (60 + rank) over the pipelines where the document appears
    candidates = k * 4
    return list(collection.aggregate([
        {"$rankFusion": {"input": {"pipelines": {
            "semantic": [vector_stage(query, candidates, filter)],
            "text": [text_stage(query, filter), {"$limit": candidates}],
        }}}},
        {"$limit": k},
        {"$project": {**FIELDS, "score": {"$meta": "score"}}},
    ]))


SEARCHES = {"semantic": semantic, "text": full_text, "hybrid": hybrid}


# ---------------------------------------------------------------- printing
def reference(doc):
    return f"vol. {doc['volume']}, cap. {doc['chapter']} ({doc['position']})"


def hits(results):
    return [{"#": rank, "fragmento": reference(doc), "score": doc["score"], "capítulo": doc["chapter_title"][:60]}
            for rank, doc in enumerate(results, start=1)]


def passage(doc, chars=400):
    print(f"[{reference(doc)}] {doc['chapter_title'][:80]}")
    print(textwrap.indent(textwrap.fill(doc["text"][:chars] + "…", 100), "    | "))
