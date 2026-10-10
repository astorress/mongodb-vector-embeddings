import time

from pymongo.operations import SearchIndexModel

from rag import config


def vector_index_definition(dimensions):
    return {
        "fields": [
            {
                "type": "vector",
                "path": "embedding",
                "numDimensions": dimensions,
                "similarity": "cosine",
            },
            # Filter fields can be used in $vectorSearch.filter (pre-filtering before the ANN search)
            {"type": "filter", "path": "volume"},
            {"type": "filter", "path": "chapter"},
        ]
    }


TEXT_INDEX_DEFINITION = {
    "mappings": {
        "dynamic": False,
        "fields": {
            "text": {"type": "string", "analyzer": "lucene.spanish"},
            "chapter_title": {"type": "string", "analyzer": "lucene.spanish"},
            "volume": {"type": "number"},
            "chapter": {"type": "number"},
        },
    }
}


def search_indexes(collection):
    return {index["name"]: index for index in collection.list_search_indexes()}


def ensure_search_index(collection, name, definition, index_type):
    existing = search_indexes(collection).get(name)
    if existing is None:
        collection.create_search_index(SearchIndexModel(definition=definition, name=name, type=index_type))
        print(f"  índice {name} ({index_type}) creado")
    elif existing.get("latestDefinition") != definition:
        collection.update_search_index(name, definition)
        print(f"  índice {name} ({index_type}) actualizado")
    else:
        print(f"  índice {name} ({index_type}) ya existe")


def wait_until_queryable(collection, names, timeout=600):
    # mongot builds indexes asynchronously from the change stream: status goes PENDING -> BUILDING -> READY
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        indexes = search_indexes(collection)
        pending = [name for name in names if not indexes.get(name, {}).get("queryable")]
        if not pending:
            return
        statuses = ", ".join(f"{name}={indexes.get(name, {}).get('status')}" for name in pending)
        print(f"  esperando índices: {statuses}")
        time.sleep(5)
    raise TimeoutError(f"Search indexes not queryable after {timeout}s: {names}")


def ensure_indexes(collection, dimensions):
    ensure_search_index(collection, config.VECTOR_INDEX, vector_index_definition(dimensions), "vectorSearch")
    ensure_search_index(collection, config.TEXT_INDEX, TEXT_INDEX_DEFINITION, "search")
    wait_until_queryable(collection, [config.VECTOR_INDEX, config.TEXT_INDEX])
