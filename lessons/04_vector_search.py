# Lección 04 - Búsqueda semántica con $vectorSearch.
#
# $vectorSearch es una etapa de agregación y debe ser la PRIMERA del pipeline. mongod se la reenvía a mongot, que
# recorre el grafo HNSW buscando los vectores más cercanos al de la pregunta, y devuelve los _id con su puntaje.
#
#   python lessons/04_vector_search.py ["otra consulta"]
import sys
import time

from lab.client import get_db
from lab.embeddings import embed_query
from lab.search import FIELDS, hits, passage, semantic, vector_stage
from lab.show import step, table, title

db = get_db()
chunks = db.chunks
query = sys.argv[1] if len(sys.argv) > 1 else "don Quijote confunde unos molinos con gigantes y los ataca"

title("04 - Búsqueda semántica")

step(f"$vectorSearch: '{query}'")
results = semantic(chunks, query, k=5)
table(hits(results))
print()
passage(results[0])
print("Los tres primeros son la aventura de los molinos (vol. 1, cap. 8): el pasaje se encuentra por su")
print("significado, sin coincidir palabra por palabra.")

step("ANN vs ENN: cuánto pierde la búsqueda aproximada según numCandidates")
vector = embed_query(query)


def run(stage):
    started = time.monotonic()
    ids = [d["_id"] for d in chunks.aggregate([stage, {"$project": {"_id": 1}}])]
    return ids, (time.monotonic() - started) * 1000


exact, exact_ms = run(vector_stage(vector, k=10, exact=True))
rows = [{"búsqueda": "exacta (exact: true)", "recall@10": 1.0, "ms": exact_ms}]
for candidates in (10, 20, 50, 200):
    ids, ms = run(vector_stage(vector, k=10, num_candidates=candidates))
    rows.append({"búsqueda": f"ANN numCandidates={candidates}", "recall@10": len(set(ids) & set(exact)) / 10, "ms": ms})
table(rows)
print("La exacta compara con todos los vectores. La aproximada (HNSW) explora solo numCandidates vecinos:")
print("con pocos puede perder alguno; con 10-20 veces el limit suele encontrarlos todos.")

step("Pre-filtros: filter dentro de $vectorSearch (campos declarados como 'filter' en el índice)")
rows = []
for f in (None, {"volume": 2}, {"chapter": {"$in": [18, 19, 20]}}, {"$and": [{"volume": 1}, {"chapter": {"$gte": 40}}]}):
    found = semantic(chunks, vector, k=5, filter=f)
    rows.append({"filter": str(f), "resultados": len(found), "fragmentos": ", ".join(d["_id"] for d in found)})
table(rows)

step("Pre-filtro vs $match posterior")
post = list(chunks.aggregate([vector_stage(vector, k=5), {"$match": {"volume": 2}}]))
pre = semantic(chunks, vector, k=5, filter={"volume": 2})
print(f"$match después de buscar: {len(post)} resultados | filter dentro de $vectorSearch: {len(pre)} resultados")
print("El filter se aplica ANTES de buscar vecinos, así que no se 'come' resultados.")

step("Después de $vectorSearch, agregación normal: capítulos que más hablan de encantadores")
table(chunks.aggregate([
    vector_stage("encantadores y hechiceros que persiguen a don Quijote", k=40, num_candidates=400),
    {"$group": {"_id": {"volume": "$volume", "chapter": "$chapter"}, "fragmentos": {"$sum": 1},
                "mejor_score": {"$max": {"$meta": "vectorSearchScore"}}, "título": {"$first": "$chapter_title"}}},
    {"$sort": {"fragmentos": -1, "mejor_score": -1}},
    {"$limit": 5},
    {"$project": {"_id": 0, "vol": "$_id.volume", "cap": "$_id.chapter", "fragmentos": 1, "mejor_score": 1,
                  "título": {"$substrCP": ["$título", 0, 50]}}},
]), ["vol", "cap", "fragmentos", "mejor_score", "título"])

step("'Más como éste': el vector de un fragmento guardado como consulta (sin usar el modelo)")
reference = chunks.find_one({"_id": "v1-c008-001"})
print(f"Referencia: vol. 1, cap. 8 - {reference['text'][:100]}…")
table(hits(chunks.aggregate([
    vector_stage(reference["embedding"], k=5, filter={"$or": [{"volume": 2}, {"chapter": {"$ne": 8}}]}),
    {"$project": {**FIELDS, "score": {"$meta": "vectorSearchScore"}}},
])))
print("Así funcionan los recomendadores: si ya tienes un vector, no necesitas el modelo para buscar.")
