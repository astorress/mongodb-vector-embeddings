# 4. Búsqueda semántica con `$vectorSearch`

```bash
python lessons/04_vector_search.py "don Quijote confunde unos molinos con gigantes y los ataca"
```

## La etapa

`$vectorSearch` es una etapa de agregación y **tiene que ser la primera** del pipeline
(`lab/search.py`):

```python
[
    {"$vectorSearch": {
        "index": "chunks_vector_index",
        "path": "embedding",
        "queryVector": embed_query(pregunta),   # la pregunta, embebida con el MISMO modelo
        "numCandidates": 100,
        "limit": 5,
        "filter": {"volume": 2},                # opcional
    }},
    {"$project": {"text": 1, "chapter": 1, "score": {"$meta": "vectorSearchScore"}}},
]
```

- **`queryVector`**: la consulta convertida en vector. Tiene que salir del mismo modelo que los
  documentos (con un modelo distinto el espacio es otro y los resultados no tienen sentido).
- **`numCandidates`**: cuántos vecinos explora el grafo HNSW antes de quedarse con los `limit` mejores.
  Más candidatos dan mejor *recall* y una consulta más lenta. Una regla habitual es usar entre 10 y 20
  veces `limit`.
- **`limit`**: cuántos resultados devuelve.
- **`exact: true`**: en vez de ANN hace una búsqueda exhaustiva (ENN). Es útil para medir cuánto
  pierde la aproximación, y no lleva `numCandidates`.
- **`filter`**: pre-filtro MQL (`$eq`, `$in`, `$gt`, `$and`, `$or`, …) sobre los campos declarados como
  `filter` en el índice. Se aplica *antes* de buscar vecinos, así que no "se come" resultados como lo
  haría un `$match` posterior.

```bash
python -c 'from lab.client import get_db; from lab.search import semantic, reference
print([reference(d) for d in semantic(get_db().chunks, "Sancho gobierna una isla", filter={"volume": 2})])'
```

## Después de `$vectorSearch`, agregación normal

Como el resultado es un pipeline normal, se puede seguir con `$group`, `$lookup` o `$sort`. Por
ejemplo, ¿en qué capítulos se habla más de encantadores?

```python
from lab.client import get_db
from lab.embeddings import embed_query

pipeline = [
    {"$vectorSearch": {"index": "chunks_vector_index", "path": "embedding",
                       "queryVector": embed_query("encantadores y hechiceros que persiguen a don Quijote"),
                       "numCandidates": 400, "limit": 40}},
    {"$group": {"_id": {"volume": "$volume", "chapter": "$chapter"}, "fragmentos": {"$sum": 1},
                "score": {"$max": {"$meta": "vectorSearchScore"}}}},
    {"$sort": {"fragmentos": -1, "score": -1}},
    {"$limit": 5},
]
for row in get_db().chunks.aggregate(pipeline):
    print(row)
```

## "Más como éste"

No siempre hace falta embeber una pregunta: se puede usar como `queryVector` el embedding de un
documento que ya existe. Así funcionan los sistemas de recomendación. Lo hace
el último paso de `lessons/04_vector_search.py`, y en mongosh está en la sección "Comandos útiles" del README.

## Limitaciones

La búsqueda semántica entiende sinónimos y paráfrasis, pero le cuestan los **nombres propios y
términos exactos** ("Rocinante", "Barataria", "Clavileño"): para el modelo son palabras raras y su
vector es poco preciso. Para eso está la búsqueda de texto completo, y por eso existe la búsqueda
híbrida ([05](05-busqueda-hibrida.md)).
