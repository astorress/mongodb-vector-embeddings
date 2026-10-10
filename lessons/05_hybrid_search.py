# Lección 05 - Texto completo ($search) y búsqueda híbrida ($rankFusion).
#
# $search busca TÉRMINOS en el índice Lucene (analizador lucene.spanish) y puntúa con BM25: gana con nombres
# propios. $vectorSearch busca SIGNIFICADO: gana con paráfrasis. $rankFusion ejecuta las dos y fusiona sus
# rankings con Reciprocal Rank Fusion: score = Σ 1 / (60 + posición del documento en cada búsqueda).
#
#   python lessons/05_hybrid_search.py ["otra consulta"]
import sys

from lab.client import get_db
from lab.config import TEXT_INDEX
from lab.search import full_text, hits, hybrid, reference, semantic, text_stage, vector_stage
from lab.show import step, table, title

db = get_db()
chunks = db.chunks

title("05 - Texto completo y búsqueda híbrida")

step("$search: 'Rocinante' (puntaje BM25, en otra escala que el coseno)")
table(hits(full_text(chunks, "Rocinante", k=3)))

step("$search con frase exacta y resaltado: 'ínsula Barataria'")
for doc in chunks.aggregate([
    {"$search": {"index": TEXT_INDEX, "phrase": {"query": "ínsula Barataria", "path": "text"},
                 "highlight": {"path": "text"}}},
    {"$limit": 3},
    {"$project": {"volume": 1, "chapter": 1, "position": 1, "highlights": {"$meta": "searchHighlights"}}},
]):
    snippet = "".join(f"**{t['value']}**" if t["type"] == "hit" else t["value"] for t in doc["highlights"][0]["texts"])
    print(f"[{reference(doc)}] …{snippet.strip()[:160]}…")

step("En qué capítulos del volumen 2 aparece más 'Dulcinea' ($search + $group)")
table(chunks.aggregate([
    text_stage("Dulcinea", filter={"volume": 2}),
    {"$group": {"_id": "$chapter", "fragmentos": {"$sum": 1}}},
    {"$sort": {"fragmentos": -1, "_id": 1}},
    {"$limit": 5},
    {"$project": {"_id": 0, "capítulo": "$_id", "fragmentos": 1}},
]), ["capítulo", "fragmentos"])

step("Cada búsqueda gana en un tipo de pregunta (top 3 de cada una)")
for question in ("¿Quién es Clavileño?", "el hidalgo pierde el juicio de tanto leer novelas de caballería"):
    print(f"\n'{question}'")
    columns = {mode: [reference(d) for d in fn(chunks, question, k=3)]
               for mode, fn in (("semántica", semantic), ("texto", full_text), ("híbrida", hybrid))}
    table([{mode: refs[i] if i < len(refs) else "" for mode, refs in columns.items()} for i in range(3)])
print("\nNinguna de las dos acierta siempre: la semántica se dispersa con nombres propios raros y el texto completo")
print("depende de que la pregunta use las palabras del libro. La híbrida sube los fragmentos que aparecen en ambas.")

query = sys.argv[1] if len(sys.argv) > 1 else "¿Qué le pasó a Sancho en la ínsula Barataria?"
step(f"$rankFusion con scoreDetails: por qué cada fragmento quedó donde quedó - '{query}'")
rows = []
for doc in chunks.aggregate([
    {"$rankFusion": {"input": {"pipelines": {
        "semantic": [vector_stage(query, k=20)],
        "text": [text_stage(query), {"$limit": 20}],
    }}, "scoreDetails": True}},
    {"$limit": 5},
    {"$project": {"volume": 1, "chapter": 1, "position": 1, "details": {"$meta": "scoreDetails"}}},
]):
    ranks = {d["inputPipelineName"]: d.get("rank", "-") for d in doc["details"]["details"]}
    rows.append({"fragmento": reference(doc), "rank semántica": ranks.get("semantic", "-"),
                 "rank texto": ranks.get("text", "-"), "score RRF": doc["details"]["value"]})
table(rows)
print("Un fragmento que aparece en las dos listas suma dos términos 1/(60 + rank) y sube al principio.")
