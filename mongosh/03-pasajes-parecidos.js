// mongosh "$MONGODB_URI" --file mongosh/03-pasajes-parecidos.js
// mongosh no puede generar embeddings, pero sí reutilizar uno guardado: "más pasajes como éste".
const quijote = db.getSiblingDB(process.env.MONGODB_DATABASE || 'quijote');

// Fragmento de referencia: la aventura de los molinos (vol. 1, cap. 8)
const reference = quijote.chunks.findOne({ volume: 1, chapter: 8, position: 1 });
print(`Referencia: vol. ${reference.volume}, cap. ${reference.chapter} - ${reference.text.slice(0, 120)}…\n`);

quijote.chunks
  .aggregate([
    {
      $vectorSearch: {
        index: 'chunks_vector_index',
        path: 'embedding',
        queryVector: reference.embedding,
        numCandidates: 200,
        limit: 6,
        // pre-filtro: excluye el propio capítulo 8 para ver pasajes parecidos en otras partes del libro
        filter: { $or: [{ volume: 2 }, { chapter: { $ne: 8 } }] },
      },
    },
    { $project: { _id: 0, volume: 1, chapter: 1, chapter_title: 1, score: { $meta: 'vectorSearchScore' } } },
  ])
  .forEach((row) => printjson(row));
