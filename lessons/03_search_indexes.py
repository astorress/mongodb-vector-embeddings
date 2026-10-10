# Lección 03 - Índices de búsqueda y mongot.
#
# Los índices normales (B-tree) viven en mongod y se actualizan en la misma escritura. Los índices de búsqueda
# (vectorial y de texto completo) viven en mongot, un proceso aparte basado en Apache Lucene, que se entera de
# cada cambio leyendo los change streams de mongod: se actualizan de forma asíncrona (consistencia eventual).
import time

from pymongo.operations import SearchIndexModel

from lab.client import get_db
from lab.config import TEXT_INDEX, VECTOR_INDEX
from lab.search import search_indexes, wait_until_queryable
from lab.show import show, step, table, title

db = get_db()
chunks = db.chunks

title("03 - Índices de búsqueda")

step("Índices normales (mongod): list_indexes")
table({"name": name, "key": str(info["key"])} for name, info in chunks.index_information().items())

step("Índices de búsqueda (mongot): list_search_indexes")
indexes = search_indexes(chunks)
table({"name": i["name"], "type": "vectorSearch" if "fields" in i["latestDefinition"] else "search",
       "status": i["status"], "queryable": i["queryable"], "docs": i.get("numDocs")} for i in indexes.values())

step("Definición del índice vectorial")
show(indexes[VECTOR_INDEX]["latestDefinition"])
print("vector: campo, dimensiones y métrica. filter: campos por los que se puede pre-filtrar en $vectorSearch.")

step("Ciclo de vida: crear un índice vectorial cuantizado (int8) y verlo construirse")
name = "chunks_vector_int8"
if name in indexes:
    chunks.drop_search_index(name)
    while name in search_indexes(chunks):
        time.sleep(1)
definition = indexes[VECTOR_INDEX]["latestDefinition"]
definition["fields"][0]["quantization"] = "scalar"
chunks.create_search_index(SearchIndexModel(definition=definition, name=name, type="vectorSearch"))
seconds = wait_until_queryable(chunks, [name])
print(f"{name} listo en {seconds:.0f} s. mongot recorrió los {chunks.estimated_document_count()} documentos.")
chunks.drop_search_index(name)
print(f"{name} borrado (drop_search_index)")

step("Consistencia eventual: un documento nuevo está en mongod al instante, en mongot un momento después")
chunks.delete_many({"_id": "prueba-consistencia"})


def in_mongot():
    return len(list(chunks.aggregate([
        {"$search": {"index": TEXT_INDEX, "text": {"query": "alígero", "path": "text"}}},
        {"$match": {"_id": "prueba-consistencia"}},
    ])))


vector = chunks.find_one({}, {"embedding": 1})["embedding"]
started = time.monotonic()
chunks.insert_one({"_id": "prueba-consistencia", "volume": 0, "chapter": 0, "text": "Clavileño el alígero",
                   "embedding": vector})
print("En mongod (find):            ", chunks.count_documents({"_id": "prueba-consistencia"}))
print("En mongot, recién insertado: ", in_mongot())
while in_mongot() == 0 and time.monotonic() - started < 30:
    time.sleep(0.05)
print(f"En mongot, {(time.monotonic() - started) * 1000:.0f} ms después:", in_mongot())
chunks.delete_one({"_id": "prueba-consistencia"})
print("Por eso el seed espera a que los índices estén 'queryable' antes de buscar.")
