// mongosh "$MONGODB_URI" --file mongosh/01-explorar.js
const quijote = db.getSiblingDB(process.env.MONGODB_DATABASE || 'quijote');

print(`Fragmentos: ${quijote.chunks.countDocuments()}`);

print('\nFragmentos por volumen:');
quijote.chunks
  .aggregate([
    { $group: { _id: '$volume', capitulos: { $addToSet: '$chapter' }, fragmentos: { $sum: 1 } } },
    { $project: { volumen: '$_id', _id: 0, capitulos: { $size: '$capitulos' }, fragmentos: 1 } },
    { $sort: { volumen: 1 } },
  ])
  .forEach((row) => printjson(row));

print('\nUn fragmento (sin el vector, que son cientos de números):');
printjson(quijote.chunks.findOne({ volume: 1, chapter: 8, position: 0 }, { embedding: 0 }));

print('\nTamaño del vector y peso en BSON de un documento:');
quijote.chunks
  .aggregate([
    { $limit: 1 },
    { $project: { dimensiones: { $size: '$embedding' }, bytes: { $bsonSize: '$$ROOT' }, bytesTexto: { $strLenBytes: '$text' } } },
  ])
  .forEach((row) => printjson(row));
