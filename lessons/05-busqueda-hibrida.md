# 5. Texto completo y búsqueda híbrida

## `$search`: palabras, no significado

```bash
python -m rag.search "Rocinante" --mode text
```

`$search` busca **términos** en el índice Lucene (`chunks_text_index`) y puntúa con BM25: pesa más un
término raro ("Clavileño") que uno común ("caballero"), y más si aparece varias veces en un fragmento
corto. Además de `text` ofrece operadores como `phrase` (frase exacta), `fuzzy` (tolera errores de
tipeo), `compound` (`must`, `should`, `filter`, `mustNot`), `highlight` y facetas. Están en
`mongosh/04-texto-completo.js`.

| | Semántica (`$vectorSearch`) | Texto completo (`$search`) |
| --- | --- | --- |
| Encuentra | paráfrasis, sinónimos, la idea | términos exactos, nombres propios |
| Falla con | nombres raros, códigos, cifras | preguntas formuladas con otras palabras |
| Score | similitud del vector (rango propio del modelo) | BM25 (sin tope) |

## Híbrida: lo mejor de ambas

```bash
python -m rag.search "¿Qué le pasó a Sancho en la ínsula Barataria?" --mode hybrid
```

Los scores de cada búsqueda no se pueden comparar (uno es un coseno y el otro BM25), así que no se
pueden sumar. La técnica estándar es **Reciprocal Rank Fusion (RRF)**, que solo usa la *posición* de
cada resultado:

```text
score(doc) = Σ  1 / (60 + posición del doc en cada lista)
```

Un fragmento que sale tercero en la semántica y primero en la de texto suma `1/63 + 1/61` y le gana a
uno que solo sale primero en una de las dos.

### `$rankFusion`: RRF dentro del servidor

Desde MongoDB 8.1 no hace falta programar la fusión: la etapa `$rankFusion` recibe varios pipelines,
los ejecuta y fusiona sus rankings con RRF. Es lo que hace `hybrid_search` (`rag/search.py`):

```python
{"$rankFusion": {"input": {"pipelines": {
    "semantic": [{"$vectorSearch": {..., "limit": 20}}],
    "text":     [{"$search": {...}}, {"$limit": 20}],
}}}},
{"$limit": 5},
{"$project": {"text": 1, "score": {"$meta": "score"}}},
```

- Cada pipeline tiene que ser una búsqueda que devuelva resultados **ordenados**: `$vectorSearch`,
  `$search`, o un `$match` + `$sort`.
- `combination.weights` permite darle más peso a una de las búsquedas, por ejemplo
  `{"semantic": 2, "text": 1}`.
- `scoreDetails: true` agrega en `{$meta: "scoreDetails"}` la posición que tuvo el documento en cada
  pipeline. Sirve para entender por qué quedó donde quedó.
- Existe también `$scoreFusion`, que en vez de posiciones combina los scores después de normalizarlos.

## Ejercicio

Compara los tres modos con preguntas que tengan nombres propios y con preguntas que no los tengan:

```bash
for m in semantic text hybrid; do python -m rag.search "¿Quién es el Caballero de la Blanca Luna?" --mode $m -k 3; done
```
