# Lección 07 - Evaluar la recuperación: ¿en qué posición aparece el capítulo que tiene la respuesta?
#
# hit@1: el fragmento correcto sale primero. hit@5: sale entre los 5 primeros. Vuelve a ejecutar esta lección cada
# vez que cambies el modelo de embeddings, el tamaño de los fragmentos o el tipo de búsqueda.
import time

from lab.client import get_db
from lab.embeddings import embed_query
from lab.search import SEARCHES
from lab.show import step, table, title

K = 5
# Questions whose answer lives in a known chapter: (question, (volume, chapter))
QUESTIONS = [
    ("¿Por qué don Quijote decide hacerse caballero andante?", (1, 1)),
    ("¿Cómo se llama el caballo de don Quijote y por qué eligió ese nombre?", (1, 1)),
    ("¿Quién arma caballero a don Quijote?", (1, 3)),
    ("¿Qué libros quemaron el cura y el barbero?", (1, 6)),
    ("¿Qué pasó con los molinos de viento?", (1, 8)),
    ("¿Qué le pasa a Sancho cuando lo mantean en la venta?", (1, 17)),
    ("¿Qué vio don Quijote en la cueva de Montesinos?", (2, 23)),
    ("¿Cómo gobierna Sancho la ínsula Barataria?", (2, 45)),
    ("¿Quién es el Caballero de la Blanca Luna y qué le exige a don Quijote?", (2, 64)),
    ("¿Cómo muere don Quijote?", (2, 74)),
]

db = get_db()

title("07 - Evaluación de la recuperación")
embed_query("calentar el modelo")  # load the model before timing

step(f"Posición del capítulo correcto con cada búsqueda ('-' = no está en los {K} primeros)")
rows, totals = [], {mode: {"hit@1": 0, f"hit@{K}": 0, "ms": 0.0} for mode in SEARCHES}
for question, expected in QUESTIONS:
    row = {"pregunta": question[:55], "esperado": f"vol. {expected[0]}, cap. {expected[1]}"}
    for mode, search in SEARCHES.items():
        started = time.monotonic()
        found = [(d["volume"], d["chapter"]) for d in search(db.chunks, question, k=K)]
        totals[mode]["ms"] += (time.monotonic() - started) * 1000 / len(QUESTIONS)
        rank = found.index(expected) + 1 if expected in found else None
        totals[mode]["hit@1"] += rank == 1
        totals[mode][f"hit@{K}"] += rank is not None
        row[mode] = rank or "-"
    rows.append(row)
table(rows)

step("Resumen")
table({"búsqueda": mode, **{k: (f"{v}/{len(QUESTIONS)}" if k != "ms" else v) for k, v in t.items()}}
      for mode, t in totals.items())
print("La híbrida suele ganar cuando las preguntas mezclan ideas y nombres propios.")
print("ms incluye calcular el embedding de la pregunta (semántica e híbrida).")
