from functools import cache

from lab.config import EMBEDDING_MODEL

# E5 models were trained with these prefixes: questions and passages live in the same space,
# but each side must be labeled or retrieval quality drops noticeably.
QUERY_PREFIX = "query: "
PASSAGE_PREFIX = "passage: "


@cache
def get_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(EMBEDDING_MODEL, device="cpu")


def dimensions():
    return get_model().get_embedding_dimension()


# normalize_embeddings=True: every vector has length 1, so cosine similarity is just the dot product
def embed_passages(texts, batch_size=64):
    return get_model().encode([PASSAGE_PREFIX + text for text in texts], batch_size=batch_size,
                              normalize_embeddings=True).tolist()


def embed_query(text):
    return get_model().encode(QUERY_PREFIX + text, normalize_embeddings=True).tolist()
