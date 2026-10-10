# Lección 01 - Embeddings: convertir texto en un vector que representa su significado.
#
# Un modelo de embeddings pone cerca los textos que dicen lo mismo, aunque usen otras palabras. La cercanía se
# mide con la similitud coseno; con vectores normalizados (largo 1) es simplemente el producto punto.
import numpy as np

from lab import book
from lab.embeddings import PASSAGE_PREFIX, QUERY_PREFIX, dimensions, embed_passages, embed_query, get_model
from lab.show import show, step, table, title

model = get_model()

title("01 - Embeddings")

step("El modelo")
show({"modelo": model.model_card_data.base_model or str(model), "dimensiones": dimensions(),
      "ventana_tokens": model.max_seq_length})

step("Un texto convertido en vector")
vector = np.array(embed_passages(["arremetió contra los molinos de viento"])[0])
print("primeros 8 números:", np.round(vector[:8], 4).tolist(), "…")
print(f"largo del vector (norma): {np.linalg.norm(vector):.4f}  -> normalizado, así coseno = producto punto")

step("Similitud: una pregunta contra varios textos")
question = "don Quijote ataca a unos gigantes"
passages = [
    "arremetió a todo galope contra los molinos de viento",
    "el caballero embistió a los enemigos que tenía delante",
    "Sancho cenó queso y pan sentado junto al fuego",
    "la factura de energía del mes de octubre",
]
q = np.array(embed_query(question))
table(sorted(({"similitud": float(q @ np.array(p)), "texto": text}
              for text, p in zip(passages, embed_passages(passages))), key=lambda r: -r["similitud"]))
print("Los textos con la misma idea quedan primero aunque no compartan palabras con la pregunta. Incluso el texto")
print("sin ninguna relación saca un puntaje alto: cada modelo tiene su propio rango, lo que importa es el ORDEN.")

step(f"Prefijos E5: '{QUERY_PREFIX}' para preguntas y '{PASSAGE_PREFIX}' para documentos")
relevant, unrelated = passages[0], passages[2]
rows = []
for label, query_text, passage_prefix in [("con prefijos", QUERY_PREFIX + question, PASSAGE_PREFIX),
                                          ("sin prefijos", question, "")]:
    qv, rv, uv = model.encode([query_text, passage_prefix + relevant, passage_prefix + unrelated],
                              normalize_embeddings=True)
    rows.append({"modo": label, "relevante": float(qv @ rv), "no relacionado": float(qv @ uv),
                 "margen": float(qv @ rv - qv @ uv)})
table(rows)
print("Los puntajes cambian según los prefijos: el modelo fue entrenado con ellos. En un par de frases el efecto puede")
print("ir en cualquier sentido; lo que se mide es la recuperación sobre todo el libro (lección 07). La regla: usar")
print("siempre la misma convención en la ingesta y en la consulta.")

step("La ventana: lo que pasa de 512 tokens se descarta sin aviso")
chapter = next(c for c in book.chapters() if c.volume == 1 and c.number == 8)
full = " ".join(chapter.paragraphs)
tokens = len(model.tokenizer(PASSAGE_PREFIX + full, verbose=False)["input_ids"])
start, end = embed_passages([full[:3000], full])
print(f"Capítulo 8 completo: {len(full)} caracteres, {tokens} tokens (ventana: {model.max_seq_length})")
print(f"similitud(primeros 3000 caracteres, capítulo completo) = {np.array(start) @ np.array(end):.4f}")
print("Son prácticamente el mismo vector: el modelo solo 'leyó' el comienzo del capítulo y descartó el resto.")
print("Por eso el libro se parte en fragmentos.")
