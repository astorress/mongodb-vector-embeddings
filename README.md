# MongoDB Vector Search

Proyecto para entender la **búsqueda semántica con MongoDB**: convertir texto en **embeddings**, guardarlos junto
a los documentos, indexarlos y buscarlos por significado con `$vectorSearch`. También incluye búsqueda de texto
completo, búsqueda híbrida y un **RAG** que responde preguntas sobre un libro real, *Don Quijote de la Mancha*
(Project Gutenberg, dominio público), usando una aplicación en Python (`pymongo` + `sentence-transformers`).

![Arquitectura del proyecto](docs/architecture.png)

> Diagrama editable: [`docs/architecture.drawio`](docs/architecture.drawio). En verde, la ingesta del libro; en azul,
> las consultas.

## 1. Conceptos de MongoDB

### ¿Qué es MongoDB?

MongoDB es una base de datos **NoSQL orientada a documentos**. En lugar de tablas con filas y columnas, guarda
**documentos** parecidos a JSON. Un documento puede tener cualquier tipo de campo, incluido un array de cientos de
números: eso permite guardar el **vector** de un texto en el mismo documento que el texto.

| Concepto | Qué es | En este proyecto |
| --- | --- | --- |
| **Database** | Contenedor lógico de colecciones. | `quijote` |
| **Collection** | Grupo de documentos, equivalente a una tabla. | `chunks`: los fragmentos del libro |
| **Document** | Un registro en formato BSON (JSON binario), de hasta 16 MB. Todo documento tiene un `_id` único. | Un fragmento de ~1200 caracteres |
| **Field** | Un par nombre-valor dentro del documento. | `text`, `chapter`, `embedding` |
| **Índice** | Estructura ordenada (B-tree) que evita recorrer toda la colección en una búsqueda exacta. | `{volume, chapter, position}` |
| **Índice de búsqueda** | Índice de Apache Lucene, separado de los normales, para búsquedas vectoriales o de texto completo. | `chunks_vector_index` y `chunks_text_index` |

Un documento de este proyecto:

```javascript
{
  _id: "v1-c008-000",                 // volumen 1, capítulo 8, fragmento 0
  volume: 1,                          // ┐ metadatos: sirven para filtrar las búsquedas
  chapter: 8,                         // ┘
  volume_title: "El ingenioso hidalgo don Quijote de la Mancha (1605)",
  chapter_title: "Del buen suceso que el valeroso don Quijote tuvo en la … aventura de los molinos de viento…",
  position: 0,
  text: "En esto, descubrieron treinta o cuarenta molinos de viento que hay en aquel campo…",
  embedding: [0.0213, -0.1131, 0.0874, …]   // 384 números: el significado de `text`
}
```

### Programas de MongoDB

| Programa | Qué hace | Aquí |
| --- | --- | --- |
| **`mongod`** | El **servidor de base de datos**: guarda los documentos, ejecuta las consultas y mantiene los índices normales. | `VectorEmbeddingsDatabase` |
| **`mongot`** | El **motor de búsqueda** (Apache Lucene): mantiene los índices vectoriales y de texto completo y resuelve `$vectorSearch` y `$search`. | `VectorEmbeddingsDatabase`, junto a `mongod` |
| **`mongosh`** | El **shell interactivo** de MongoDB, en JavaScript: `db.chunks.find()`, `db.chunks.getSearchIndexes()`. | En `VectorEmbeddingsRag` |
| **Driver (`pymongo`)** | Biblioteca con la que la aplicación habla con MongoDB. | Los scripts `rag.*` |

### Cómo funciona la base de datos por dentro

La búsqueda vectorial la resuelven **dos procesos** que trabajan juntos:

```text
                  aplicación (pymongo / mongosh)
                              │  aggregate([{ $vectorSearch: … }])
                              ▼
                           mongod ────── gRPC: "busca esto" ──────► mongot (Lucene)
                    (guarda documentos)  ◄── ids + puntajes ─────── (guarda índices)
                              │                                        ▲
                              └──────── change streams (oplog) ────────┘
                                   mongot se entera de cada cambio
```

- **La aplicación solo habla con `mongod`.** `mongod` no sabe buscar vectores: le reenvía `$vectorSearch` y
  `$search` a `mongot`, recibe los `_id` más cercanos con su puntaje y devuelve los documentos completos.
- **`mongot` se mantiene al día solo.** Lee cada inserción, actualización o borrado de `mongod` mediante
  *change streams* y actualiza sus índices. Lo hace de forma **asíncrona**: un documento recién insertado tarda
  un momento en aparecer en las búsquedas (consistencia eventual). Los índices normales de `mongod`, en cambio,
  se actualizan en la misma escritura.
- **Por qué hace falta un replica set.** Los change streams leen el *oplog*, el registro de cambios que solo
  existe en un replica set. Por eso `mongod` corre como **replica set de un solo nodo**: tiene oplog, pero sigue
  siendo una sola base de datos, sin copias ni sharding.
- **`mongot` no guarda tus datos.** Si se borran sus índices, los reconstruye leyendo `mongod`.

## 2. Búsqueda semántica y vector embeddings

### Embeddings

Un **embedding** es una lista de números (un vector) que representa el **significado** de un texto. Un modelo
entrenado para esto pone cerca textos que dicen lo mismo con otras palabras, aunque no compartan ninguna:

```text
"don Quijote ataca a unos gigantes"        → [ 0.021, -0.113,  0.087, …]  ┐ cerca: misma idea
"arremetió contra los molinos de viento"   → [ 0.019, -0.098,  0.091, …]  ┘
"Sancho cena queso y pan"                  → [-0.140,  0.054, -0.012, …]    lejos
```

| Pieza | Qué es | En este proyecto |
| --- | --- | --- |
| **Modelo de embeddings** | Red neuronal que convierte texto en un vector. La pregunta y los documentos **deben** pasar por el mismo modelo, o sus vectores no son comparables. | `intfloat/multilingual-e5-small`, en CPU, sin API key |
| **Dimensiones** | Cuántos números tiene cada vector. El índice debe declarar exactamente la misma cantidad. | 384 |
| **Similitud** | Cómo se mide la cercanía entre dos vectores: `cosine` (el ángulo), `dotProduct` (producto punto, exige vectores normalizados) o `euclidean` (distancia). | `cosine`, con vectores normalizados |
| **Prefijos** | Los modelos E5 esperan `query: ` delante de las preguntas y `passage: ` delante de los textos indexados. | `rag/embeddings.py` |
| **Ventana** | Máximo de tokens que el modelo lee; lo que sobra se descarta sin aviso. | 512 tokens |

### Chunking: partir el texto

Un capítulo entero no cabe en la ventana del modelo, y aunque cupiera, un solo vector para tantos temas a la vez
sería demasiado genérico. Por eso el libro se parte en **fragmentos** (*chunks*), y cada uno tiene su propio
vector. Este proyecto junta párrafos completos hasta ~1200 caracteres (unos 300 tokens), parte por frases los
párrafos más largos y **solapa** un párrafo entre fragmentos consecutivos, para que una idea cortada en el borde
quede completa en uno de los dos. Resultado: 126 capítulos → **2424 fragmentos**.

### El índice vectorial

```javascript
{
  fields: [
    { type: "vector", path: "embedding", numDimensions: 384, similarity: "cosine" },
    { type: "filter", path: "volume" },      // campos por los que se podrá pre-filtrar
    { type: "filter", path: "chapter" }
  ]
}
```

`mongot` organiza los vectores en un grafo **HNSW** (*Hierarchical Navigable Small World*): cada vector queda
conectado con sus vecinos cercanos, en varios niveles. Para buscar, recorre el grafo saltando hacia vectores cada
vez más parecidos a la consulta, **sin compararla con todos**. Es una búsqueda **aproximada** (ANN): muy rápida,
pero puede perderse algún vecino real.

### `$vectorSearch`

Es una etapa de agregación y debe ser la **primera** del pipeline:

```javascript
db.chunks.aggregate([
  { $vectorSearch: {
      index: "chunks_vector_index",
      path: "embedding",
      queryVector: [ … ],          // la pregunta, convertida con el MISMO modelo
      numCandidates: 100,          // vecinos que explora el grafo HNSW
      limit: 5,                    // resultados que devuelve
      filter: { volume: 2 }        // opcional: pre-filtro por campos tipo "filter"
  } },
  { $project: { text: 1, chapter: 1, score: { $meta: "vectorSearchScore" } } }
])
```

| Parámetro | Qué controla |
| --- | --- |
| **`numCandidates`** | Cuántos candidatos explora el grafo antes de quedarse con los mejores. Más candidatos = mejor *recall*, pero más lento. Lo habitual es de 10 a 20 veces `limit`. |
| **`limit`** | Cuántos documentos devuelve. |
| **`filter`** | Pre-filtro con operadores MQL (`$eq`, `$in`, `$gte`, `$and`…) sobre los campos declarados como `filter`. Se aplica **antes** de buscar vecinos, así que no reduce la cantidad de resultados como lo haría un `$match` posterior. |
| **`exact: true`** | Búsqueda exacta (ENN): compara con todos los vectores. Sirve para medir cuánto pierde la aproximación. |
| **`vectorSearchScore`** | Puntaje de similitud de cada resultado. Cada modelo tiene su propio rango; lo que importa es el **orden**. |

Después de `$vectorSearch` el pipeline sigue siendo normal: `$group`, `$lookup`, `$sort`, etc.

### Semántica, texto completo e híbrida

| Búsqueda | Etapa | Encuentra | Le cuesta |
| --- | --- | --- | --- |
| **Semántica** | `$vectorSearch` | Paráfrasis, sinónimos, la idea aunque se diga con otras palabras | Nombres propios y términos raros ("Clavileño", "Barataria") |
| **Texto completo** | `$search` | Términos exactos y nombres propios. Usa el analizador `lucene.spanish` (ignora tildes, plurales y palabras vacías) y puntúa con **BM25** | Preguntas formuladas con palabras distintas a las del texto |
| **Híbrida** | `$rankFusion` | Lo mejor de ambas: ejecuta las dos búsquedas y fusiona sus rankings | — |

Los puntajes de las dos búsquedas no se pueden comparar (uno es un coseno y el otro BM25), así que `$rankFusion`
usa **Reciprocal Rank Fusion**, que solo mira la **posición** de cada documento en cada lista:

```text
score(doc) = Σ  1 / (60 + posición del doc en cada búsqueda)
```

Un fragmento que sale tercero en la semántica y primero en la de texto suma `1/63 + 1/61`, y le gana a uno que solo
aparece primero en una de las dos. `$rankFusion` existe desde MongoDB 8.1.

### RAG: recuperar, aumentar, generar

**RAG** (*Retrieval-Augmented Generation*) es responder preguntas con un modelo de lenguaje dándole como contexto
los fragmentos recuperados de tu base de datos:

```text
pregunta ──► 1. Recuperar ──────────► 2. Aumentar ────────────────► 3. Generar
             búsqueda híbrida          prompt = instrucciones         el LLM responde
             en MongoDB                + fragmentos + pregunta        citando [1], [2]…
```

La calidad depende sobre todo del paso 1: si el fragmento con la respuesta no llega al prompt, el modelo no
puede usarlo. Aquí el paso 3 usa Claude y es opcional (requiere API key).

### Las decisiones que más afectan la calidad

| Decisión | Efecto | En este proyecto |
| --- | --- | --- |
| **Modelo de embeddings** | Tiene que entender el idioma y el tipo de texto. Más dimensiones no siempre es mejor. | `multilingual-e5-small` (384). `multilingual-e5-base` (768) no acertó más y tardó 2,6 veces más en procesar el libro. |
| **Tamaño del fragmento** | Muy chico pierde contexto; muy grande diluye el significado. | ~1200 caracteres con solapamiento de un párrafo |
| **Tipo de búsqueda** | La híbrida suele ganar cuando las preguntas mezclan ideas y nombres propios. | Híbrida: 7/10 aciertos en primer lugar, contra 5/10 de la semántica |
| **`numCandidates`** | Más candidatos mejora el *recall* a cambio de velocidad. | 20 × `limit` |
| **Metadatos para filtrar** | Permiten acotar la búsqueda (por volumen, capítulo, fecha, cliente…) dentro del mismo índice. | `volume` y `chapter` |

Cada decisión se puede medir con `python -m rag.evaluate` (ver [lecciones](#5-lecciones)).

## 3. Cómo está armado el proyecto

| Contenedor | Proceso | Puerto interno | Puerto en el host | Rol |
| --- | --- | --- | --- | --- |
| `VectorEmbeddingsDatabase` | `mongod` + `mongot` (imagen `mongodb/mongodb-atlas-local`, MongoDB 8.3) | 27017 | 27027 | La base de datos vectorial |
| `VectorEmbeddingsRag` | Python 3.13 · pymongo · sentence-transformers · mongosh | — | — | Donde se ejecutan la ingesta, las búsquedas y las lecciones |

**Arranque:**

1. `.docker/initialize.sh` genera `.envs/mongo.env` con un usuario `root` y una contraseña aleatoria.
2. Se inicia `VectorEmbeddingsDatabase`: crea el usuario, arranca `mongod` como replica set de un nodo y luego
   `mongot`.
3. Cuando la base está sana, se inicia `VectorEmbeddingsRag`.
4. `python -m rag.ingest` (una sola vez) carga el libro y crea los índices.

Los datos, los índices de `mongot` y el modelo de embeddings descargado se guardan en volúmenes, así que
sobreviven a reinicios.

La aplicación se conecta con `MONGODB_URI` (en `.envs/mongo.env`):
`mongodb://root:<contraseña>@vector_embeddings_database:27017/?directConnection=true&authSource=admin` dentro de
Docker, y con el mismo usuario en `localhost:27027` desde el host.

```text
.devcontainer.json            # Dev Container de VS Code
.docker/
  Dockerfile                  # img-base (Python + Node + mongosh) -> img-rag (torch CPU + requirements)
  docker-compose.yml          # VectorEmbeddingsDatabase y VectorEmbeddingsRag
  initialize.sh               # Genera .envs/mongo.env
  entrypoint.sh               # Descarga el modelo de embeddings (devcontainer)
.envs/mongo.env               # MONGODB_URI, credenciales y modelo (generado, no se versiona)
data/don_quijote.txt          # El libro (Project Gutenberg #2000)
docs/architecture.drawio      # Diagrama
src/rag/                      # embeddings, book, chunking, indexes, ingest, search, ask, evaluate
mongosh/                      # Scripts 01-05 para la shell
lessons/                      # Teoría 01-06
tests/                        # Parser y chunking
```

## 4. Puesta en marcha

**Con VS Code**: `Dev Containers: Reopen in Container`.

**Con la terminal**:

```bash
.docker/initialize.sh                                        # solo la primera vez
docker compose -f .docker/docker-compose.yml up -d --build
docker exec -it VectorEmbeddingsRag bash                     # entrar al contenedor
```

Dentro del contenedor (`/app`):

```bash
python -m rag.ingest           # siempre primero (2-3 min la primera vez: descarga el modelo y embebe 2424 fragmentos)
python -m rag.search "don Quijote pelea contra gigantes"
mongosh "$MONGODB_URI"         # shell interactivo
```

Para que `rag.ask` genere respuestas con Claude, crea `.envs/anthropic.env` con `ANTHROPIC_API_KEY=...` y vuelve a
ejecutar el `docker compose ... up -d`. Sin API key, `rag.ask` recupera los fragmentos y muestra el prompt.

### Abrir la base en MongoDB Compass

**New Connection** → pega la URI → **Save & Connect**. La contraseña está en `.envs/mongo.env`:

```text
mongodb://root:<MONGODB_INITDB_ROOT_PASSWORD>@localhost:27027/?directConnection=true&authSource=admin
```

- **`directConnection=true` es necesario**: sin él, Compass le pregunta a `mongod` por su replica set, recibe el
  nombre interno del contenedor (`mongodb:27017`), que tu equipo no conoce, y la conexión falla.
- En `quijote.chunks` ves los 2424 fragmentos con su vector. En la pestaña **Indexes → Search Indexes** aparecen
  los dos índices de búsqueda, y desde **Aggregations** puedes probar `$search` directamente.

Borrar todo, incluidos los datos y el modelo descargado:

```bash
docker compose -f .docker/docker-compose.yml down -v
```

## 5. Lecciones

Todo se ejecuta dentro de `VectorEmbeddingsRag`. La teoría de cada tema está en [`lessons/`](lessons).

| Comando | Qué hace | Qué observar |
| --- | --- | --- |
| `python -m rag.ingest` | Parsea el libro en 126 capítulos, lo parte en 2424 fragmentos, calcula los embeddings y los guarda con `bulk_write` (upsert por `_id`). Crea los dos índices de búsqueda y espera a que estén listos. | Los índices pasan de `PENDING` a listos mientras `mongot` los construye. Si la carga se corta, al relanzarla solo procesa lo que falta. `--reset` empieza de cero y `--max-chars` cambia el tamaño del fragmento. |
| `python -m rag.search "<consulta>"` | Búsqueda **semántica** con `$vectorSearch`. | Encuentra la aventura de los molinos aunque preguntes por "gigantes" sin decir "molinos". |
| `python -m rag.search "<consulta>" --mode text` | Búsqueda de **texto completo** con `$search`. | Gana cuando buscas un nombre propio (`"Rocinante"`, `"Clavileño"`). Los puntajes son BM25, en otra escala. |
| `python -m rag.search "<consulta>" --mode hybrid` | Búsqueda **híbrida** con `$rankFusion`. | Los fragmentos que aparecen en las dos búsquedas suben al principio. |
| `python -m rag.search "<consulta>" --volume 2 --chapter 45 -k 3` | Pre-filtros por metadatos dentro de `$vectorSearch`. | Solo devuelve fragmentos de ese volumen o capítulo, sin perder resultados. |
| `python -m rag.ask "<pregunta>"` | **RAG**: recupera fragmentos (híbrida), arma el prompt y, si hay API key, Claude responde citándolos. `--no-llm` se detiene en el prompt; `--show-prompt` lo muestra siempre. | Cada fragmento llega numerado y con su referencia (volumen, capítulo), para que la respuesta pueda citarlos. |
| `python -m rag.evaluate` | Hace 10 preguntas cuya respuesta está en un capítulo conocido y mide en qué posición aparece con cada modo. | *hit@1* (sale primero) y *hit@5* (entre los 5 primeros). Vuelve a correrlo cada vez que cambies el modelo, el chunking o la búsqueda. |
| `mongosh "$MONGODB_URI" --file mongosh/01-explorar.js` | Cuenta los fragmentos por volumen, muestra un documento sin su vector y cuánto pesa. | El vector pesa más que el texto: ~5 KB contra ~1 KB. |
| `mongosh "$MONGODB_URI" --file mongosh/02-indices.js` | Lista los índices de búsqueda con su estado y definición. | `status: READY` y `queryable: true`. |
| `mongosh "$MONGODB_URI" --file mongosh/03-pasajes-parecidos.js` | "Más como éste": usa el vector de un fragmento guardado (los molinos) como consulta, con un pre-filtro que excluye su propio capítulo. | No hace falta un modelo para buscar si ya tienes un vector. Así funcionan los recomendadores. |
| `mongosh "$MONGODB_URI" --file mongosh/04-texto-completo.js` | `$search` con frase exacta y resaltado (`"ínsula Barataria"`), y en qué capítulos aparece más "Dulcinea". | `searchHighlights` marca las palabras encontradas dentro del fragmento. |
| `mongosh "$MONGODB_URI" --file mongosh/05-consistencia-eventual.js` | Inserta un documento y lo busca con `$search` hasta que aparece. | `find` lo ve al instante; `mongot`, un momento después (consistencia eventual). |
| `pytest` | Prueba el parser (126 capítulos, 2 volúmenes) y el chunking (tamaño, solapamiento). | No necesita la base de datos. |

| Teoría | Tema |
| --- | --- |
| [01](lessons/01-embeddings.md) | Qué es un embedding, similitud y el modelo |
| [02](lessons/02-ingesta-y-chunking.md) | Ingesta, chunking y el documento |
| [03](lessons/03-indices-de-busqueda.md) | Índices de búsqueda y `mongot` |
| [04](lessons/04-busqueda-semantica.md) | `$vectorSearch`, filtros y "más como éste" |
| [05](lessons/05-busqueda-hibrida.md) | Texto completo, `$rankFusion` y RRF |
| [06](lessons/06-rag.md) | RAG y evaluación |

## 6. Comandos útiles

En `mongosh "$MONGODB_URI"`:

```javascript
use quijote
db.chunks.countDocuments()                                // 2424 fragmentos
db.chunks.findOne({ chapter: 8 }, { embedding: 0 })       // un documento sin el vector
db.chunks.getSearchIndexes()                              // índices de búsqueda: status y definición

// Búsqueda semántica con el vector de un fragmento guardado (no hace falta el modelo)
const ref = db.chunks.findOne({ _id: "v1-c008-001" })
db.chunks.aggregate([
  { $vectorSearch: { index: "chunks_vector_index", path: "embedding", queryVector: ref.embedding,
                     numCandidates: 100, limit: 5, filter: { volume: 2 } } },
  { $project: { chapter: 1, chapter_title: 1, score: { $meta: "vectorSearchScore" } } }
])

// Lo mismo, pero exacta (ENN): compara con los 2424 vectores
db.chunks.aggregate([
  { $vectorSearch: { index: "chunks_vector_index", path: "embedding", queryVector: ref.embedding,
                     exact: true, limit: 5 } },
  { $project: { chapter: 1, score: { $meta: "vectorSearchScore" } } }
])

// Texto completo
db.chunks.aggregate([
  { $search: { index: "chunks_text_index", text: { query: "Rocinante", path: "text" } } },
  { $limit: 3 },
  { $project: { chapter: 1, score: { $meta: "searchScore" } } }
])
```

Experimento: consistencia eventual. Un documento nuevo está en `mongod` al instante, pero `mongot` tarda un
momento en indexarlo:

```bash
docker exec VectorEmbeddingsRag bash -c 'mongosh "$MONGODB_URI" --quiet --file mongosh/05-consistencia-eventual.js'
#   -> En mongod (find):            1
#   -> En mongot, recién insertado: 0
#   -> En mongot, 250 ms después:   1
```

El script inserta un documento, lo busca con `$search` hasta que aparece y luego lo borra.

## Notas

- **Credenciales locales**: la base tiene autenticación (usuario `root` con contraseña aleatoria en
  `.envs/mongo.env`, que no se versiona) y se publica solo en `localhost:27027`. Es para aprender en local; en
  producción se usan usuarios con roles mínimos y TLS.
- **Imagen `mongodb-atlas-local`**: trae `mongod` y `mongot` en un solo contenedor y es la forma oficial de probar
  Vector Search en local. Se usa la etiqueta `preview` (MongoDB 8.3), fijada por digest para que no cambie sola.
  MongoDB 9 Community también tiene Vector Search, pero requiere `mongot` en un contenedor aparte.
- **Sin GPU**: el modelo de embeddings corre en CPU (`torch` CPU). Es suficiente para un libro; para millones de
  documentos se usa GPU o un servicio de embeddings.
