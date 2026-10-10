# 6. RAG: recuperar, aumentar, generar

**RAG** (*Retrieval-Augmented Generation*) es responder una pregunta con un LLM, pero dándole como
contexto los fragmentos relevantes recuperados de tu base de datos. Así el modelo responde sobre *tus*
datos, cita de dónde sale cada cosa y no tiene que adivinar.

```bash
python -m rag.ask "¿Cómo se llama el caballo de don Quijote y por qué eligió ese nombre?"
```

```text
pregunta ──► 1. Recuperar ──────────► 2. Aumentar ─────────────► 3. Generar
             búsqueda híbrida          prompt = instrucciones      Claude responde citando
             (lecciones 4 y 5)         + <fragmentos> + pregunta   [1], [2]…
```

## 1. Recuperar

Es todo lo que vimos: `search(pregunta, mode="hybrid", k=5)`. La calidad del RAG depende sobre todo
de este paso. Si el fragmento con la respuesta no llega al prompt, ningún LLM la va a inventar bien.

## 2. Aumentar

`build_prompt` (`rag/ask.py`) arma el mensaje con los fragmentos numerados y su referencia:

```xml
<fragmentos>
<fragmento numero="1" referencia="Vol. 1, cap. 1 (fragmento 4)" capitulo="Que trata de la condición…">
…Cuatro días se le pasaron en imaginar qué nombre le pondría…
</fragmento>
…
</fragmentos>

Pregunta: ¿Cómo se llama el caballo de don Quijote…?
```

El *system prompt* le pide responder **solo** con esos fragmentos, citar cada afirmación con `[n]` y
decir si no le alcanzan. Eso es lo que convierte a un LLM genérico en un buscador con respuestas
verificables.

Para ver el prompt sin llamar a ningún LLM:

```bash
python -m rag.ask "¿Quién es Dulcinea?" --no-llm
```

## 3. Generar (opcional, con Claude)

Si existe `.envs/anthropic.env` con `ANTHROPIC_API_KEY=...`, `rag.ask` envía el prompt a Claude
(`claude-opus-5-5`) con el SDK oficial `anthropic` y muestra la respuesta en streaming. Sin API key, el
proyecto igual recupera y muestra el prompt aumentado: los pasos 1 y 2, que son la parte de MongoDB,
funcionan completos.

```bash
echo "ANTHROPIC_API_KEY=sk-ant-..." > .envs/anthropic.env
docker compose -f .docker/docker-compose.yml up -d   # recrea el contenedor con la nueva variable
```

## Qué mejorar a partir de aquí

- **Evaluar**: `python -m rag.evaluate` corre 10 preguntas cuya respuesta está en un capítulo conocido
  y mide *hit@1* y *hit@k* (¿el capítulo correcto sale primero? ¿y entre los k primeros?) en los tres
  modos. Con `multilingual-e5-small` la híbrida acierta 7/10 en primer lugar, la de texto 6/10 y la
  semántica 5/10 (puede variar un punto entre cargas, porque HNSW es aproximado). Vuelve a correrla cada vez que cambies el chunking, el modelo o
  `numCandidates`, y agrega tus propias preguntas a `QUESTIONS`. (`multilingual-e5-base`, con el doble
  de dimensiones, no mejoró estos números y tarda 2,6 veces más en embeber el libro.)
- **Reranking**: recupera 30 candidatos y reordénalos con un modelo *cross-encoder* antes de quedarte
  con 5.
- **Contexto vecino**: cuando un fragmento es relevante, agrega al prompt también el anterior y el
  siguiente (`position ± 1`, que es una consulta trivial gracias al índice `volume, chapter,
  position`).
- **Automated embedding**: `mongot` puede generar los embeddings por ti con modelos de Voyage AI (en
  preview). Defines el campo de texto en el índice y te olvidas de `rag/embeddings.py`.
