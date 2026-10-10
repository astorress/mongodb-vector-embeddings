# 2. Ingesta: del libro a documentos con vectores

`python -m rag.ingest` hace todo el recorrido:

```text
data/don_quijote.txt ──► rag/book.py ──► rag/chunking.py ──► rag/embeddings.py ──► MongoDB
   (Gutenberg)          126 capítulos      fragmentos         un vector por        colección
                                           ~1200 caracteres   fragmento            quijote.chunks
```

## 1. Parseo (`rag/book.py`)

El texto de Project Gutenberg trae una licencia al inicio y al final, preliminares (tasa, prólogos,
poemas) y los capítulos. El parser se queda solo con los capítulos (`Capítulo VIII. Del buen suceso…`),
convierte el número romano y detecta el segundo volumen (1615) cuando la numeración vuelve a empezar.

## 2. Chunking (`rag/chunking.py`)

Un capítulo completo no cabe en la ventana del modelo, y aunque cupiera un solo vector diluiría muchos
temas a la vez. Hay que partirlo. La estrategia de este proyecto es:

- juntar **párrafos completos** hasta ~1200 caracteres (unos 300 tokens);
- partir por frases los párrafos que superan ese tamaño (en el Quijote hay párrafos larguísimos);
- **solapar** un párrafo entre fragmentos consecutivos, para que una idea cortada en el límite quede
  completa en al menos uno de los dos.

Es la decisión que más afecta a la calidad de un RAG: con fragmentos muy chicos se pierde contexto y
con fragmentos muy grandes el vector se vuelve genérico. Prueba con `--max-chars 600` o `2000`
(usando `--reset`) y compara las búsquedas.

## 3. El documento

Cada fragmento queda así en MongoDB (`mongosh/01-explorar.js`):

```js
{
  _id: 'v1-c008-000',            // volumen-capítulo-posición: ID estable y legible
  volume: 1,
  volume_title: 'El ingenioso hidalgo don Quijote de la Mancha (1605)',
  chapter: 8,
  chapter_title: 'Del buen suceso que el valeroso don Quijote tuvo en la … aventura de los molinos de viento…',
  position: 0,
  text: 'En esto, descubrieron treinta o cuarenta molinos de viento…',
  embedding: [0.0213, -0.1131, …]  // el vector
}
```

El texto, sus metadatos y su vector viven **en el mismo documento**. Esa es la gracia de usar MongoDB
como base vectorial: no hay que sincronizar una base vectorial aparte con la base de datos
"de verdad", y los metadatos sirven como filtro en la misma consulta.

## 4. Carga idempotente

La ingesta usa `bulk_write` con `ReplaceOne(..., upsert=True)` por `_id`, y antes consulta qué
fragmentos ya tienen `embedding`. Si se corta a la mitad, al volver a ejecutarla continúa donde iba.
`--reset` borra la colección y empieza de cero.

## Para pensar

- ¿Qué pasa si corriges un error de tipeo en un fragmento? Hay que recalcular **su** embedding:
  el vector deja de corresponder al texto.
- Los vectores pesan: una lista de Python se guarda como 384 *doubles* de 8 bytes (≈ 5 KB por
  documento en BSON, cuatro veces el propio texto). Guardarlo como vector BSON (`binData`, con
  `Binary.from_vector` de pymongo) en `float32` lo deja a la mitad; en `int8`, a un octavo, y en `bit`,
  a 1/64. El índice también puede cuantizar por su cuenta (`"quantization": "scalar"` o `"binary"`).
