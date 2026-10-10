// mongosh "$MONGODB_URI" --file mongosh/02-indices.js
// Los índices de búsqueda NO viven en mongod: los construye y guarda mongot (Lucene).
const quijote = db.getSiblingDB(process.env.MONGODB_DATABASE || 'quijote');

quijote.chunks.getSearchIndexes().forEach((index) => {
  print(`\n${index.name}  type=${index.type}  status=${index.status}  queryable=${index.queryable}`);
  printjson(index.latestDefinition);
});

// Así se crearía a mano el índice vectorial (rag.ingest ya lo hace):
//
// quijote.chunks.createSearchIndex({
//   name: 'chunks_vector_index',
//   type: 'vectorSearch',
//   definition: {
//     fields: [
//       { type: 'vector', path: 'embedding', numDimensions: 384, similarity: 'cosine' },
//       { type: 'filter', path: 'volume' },
//       { type: 'filter', path: 'chapter' },
//     ],
//   },
// });
