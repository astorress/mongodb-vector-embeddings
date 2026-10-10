from functools import cache

from rag import config

# E5 models were trained with these prefixes: questions and passages live in the same space,
# but each side must be labeled or retrieval quality drops noticeably.
QUERY_PREFIX = "query: "
PASSAGE_PREFIX = "passage: "


@cache
def get_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(config.EMBEDDING_MODEL, device="cpu")


def dimensions():
    return get_model().get_embedding_dimension()


def embed_passages(texts, batch_size=64):
    vectors = get_model().encode([PASSAGE_PREFIX + text for text in texts],
                                 batch_size=batch_size,
                                 normalize_embeddings=True)
    return vectors.tolist()


def embed_query(text):
    vector = get_model().encode(QUERY_PREFIX + text, normalize_embeddings=True)
    return vector.tolist()
