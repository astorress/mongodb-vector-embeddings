// mongosh "$MONGODB_URI" --file mongosh/05-consistencia-eventual.js
// Un documento nuevo está en mongod al instante, pero mongot lo indexa unos instantes después.
const chunks = db.getSiblingDB(process.env.MONGODB_DATABASE || 'quijote').chunks;

const found = () =>
  chunks
    .aggregate([
      { $search: { index: 'chunks_text_index', text: { query: 'alígero', path: 'text' } } },
      { $match: { _id: 'prueba-consistencia' } },
    ])
    .toArray().length;

chunks.deleteOne({ _id: 'prueba-consistencia' });
chunks.insertOne({
  _id: 'prueba-consistencia',
  volume: 9,
  chapter: 1,
  text: 'Clavileño el alígero',
  embedding: chunks.findOne({}, { embedding: 1 }).embedding,
});

print(`En mongod (find):            ${chunks.countDocuments({ _id: 'prueba-consistencia' })}`);
print(`En mongot, recién insertado: ${found()}`);
let waited = 0;
while (found() === 0 && waited < 30000) {
  sleep(250);
  waited += 250;
}
print(`En mongot, ${waited} ms después: ${found()}`);

chunks.deleteOne({ _id: 'prueba-consistencia' });
