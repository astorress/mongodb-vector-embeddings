# 3. Índices de búsqueda y `mongot`

## Dos procesos

```text
            aggregate($vectorSearch / $search)
  pymongo ───────────────────────────────────► mongod ──gRPC──► mongot (Lucene)
                                                 ▲                 │
                                                 └─ change streams ┘  mongot replica los datos
                                                                      y mantiene sus índices
```

- **`mongod`** es la base de datos de siempre: guarda documentos y resuelve consultas MQL.
- **`mongot`** es un proceso aparte, basado en Apache Lucene, que mantiene los índices de búsqueda
  (vectorial y de texto). No guarda tus datos: si se borran sus índices, los reconstruye leyendo
  `mongod`.
- El cliente **solo habla con `mongod`**, que reenvía a `mongot` las etapas `$vectorSearch`, `$search`
  y `$searchMeta`.

En este proyecto los dos procesos corren **dentro del mismo contenedor**, `MongoVectorSearch`
(imagen oficial `mongodb/mongodb-atlas-local`), así que desde fuera es una sola base de datos.

`mongot` lee los cambios de `mongod` con *change streams*, que solo existen sobre el *oplog* de un
replica set. Por eso la imagen configura internamente a `mongod` como **replica set de un solo nodo**,
con el nombre del *hostname* del contenedor (`mongodb`, fijado en el compose para que los datos
sobrevivan si se recrea el contenedor). Sigue siendo una única base de datos, solo que con oplog.

Consecuencia práctica: después de insertar, el índice tarda un momento en reflejar los cambios
(consistencia eventual). Por eso `lab/search.py` (`wait_until_queryable`) espera a que el índice esté `queryable`.

## El índice vectorial

```python
{
    "fields": [
        {"type": "vector", "path": "embedding", "numDimensions": 384, "similarity": "cosine"},
        {"type": "filter", "path": "volume"},
        {"type": "filter", "path": "chapter"},
    ]
}
```

- `vector`: el campo con el embedding, sus dimensiones y la métrica.
- `filter`: los campos por los que se podrá **pre-filtrar** dentro de `$vectorSearch`. Un campo que no
  esté declarado aquí no se puede usar en `filter`.

Por dentro, `mongot` construye un grafo **HNSW** (*Hierarchical Navigable Small World*). Permite
encontrar vecinos cercanos sin comparar la consulta contra los 2400 vectores (búsqueda aproximada,
ANN).

## El índice de texto completo

```python
{
    "mappings": {
        "dynamic": False,
        "fields": {
            "text": {"type": "string", "analyzer": "lucene.spanish"},
            "chapter_title": {"type": "string", "analyzer": "lucene.spanish"},
            "volume": {"type": "number"},
            "chapter": {"type": "number"},
        },
    }
}
```

El analizador `lucene.spanish` pasa el texto a minúsculas, quita *stopwords* ("el", "de", "que") y
reduce las palabras a su raíz (*stemming*: "molinos" y "molino" coinciden). La relevancia se calcula
con BM25.

## Crear, ver y cambiar índices

| pymongo | mongosh |
| --- | --- |
| `collection.create_search_index(SearchIndexModel(..., type="vectorSearch"))` | `db.chunks.createSearchIndex({...})` |
| `collection.list_search_indexes()` | `db.chunks.getSearchIndexes()` |
| `collection.update_search_index(name, definition)` | `db.chunks.updateSearchIndex(name, definition)` |
| `collection.drop_search_index(name)` | `db.chunks.dropSearchIndex(name)` |

Revisa el estado y el ciclo de vida de un índice con `python lessons/03_search_indexes.py`.
