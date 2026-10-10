from functools import cache

from pymongo import MongoClient

from rag import config


@cache
def get_client():
    return MongoClient(config.MONGODB_URI)


def get_database():
    return get_client()[config.MONGODB_DATABASE]


def get_chunks():
    return get_database()[config.CHUNKS_COLLECTION]
