# Lección 06 - RAG: recuperar, aumentar, generar.
#
#   1. Recuperar: búsqueda híbrida en MongoDB (lecciones 04 y 05).
#   2. Aumentar: el prompt lleva instrucciones + los fragmentos numerados con su referencia + la pregunta.
#   3. Generar: Claude responde usando solo esos fragmentos y citándolos [1], [2]… (opcional: requiere API key
#      en .envs/anthropic.env; sin ella la lección se detiene en el prompt).
#
#   python lessons/06_rag.py ["otra pregunta"]
import sys

from lab.client import get_db
from lab.config import CLAUDE_MODEL
from lab.rag import SYSTEM_PROMPT, build_prompt, generate, has_credentials
from lab.search import hits, hybrid
from lab.show import step, table, title

db = get_db()
question = sys.argv[1] if len(sys.argv) > 1 else "¿Cómo se llama el caballo de don Quijote y por qué eligió ese nombre?"

title("06 - RAG")
print("Pregunta:", question)

step("1. Recuperar: búsqueda híbrida, 5 fragmentos")
results = hybrid(db.chunks, question, k=5)
table(hits(results))

step("2. Aumentar: el prompt que recibe el modelo")
prompt = build_prompt(question, results)
print(f"system: {len(SYSTEM_PROMPT)} caracteres | user: {len(prompt)} caracteres\n")
print(prompt[:1500] + ("\n[…]" if len(prompt) > 1500 else ""))

step(f"3. Generar: respuesta de {CLAUDE_MODEL}")
if has_credentials():
    generate(prompt)
else:
    print("(Sin ANTHROPIC_API_KEY: crea .envs/anthropic.env y recrea el contenedor para generar la respuesta.)")
    print("Los pasos 1 y 2, que son la parte de MongoDB, ya están completos.")
