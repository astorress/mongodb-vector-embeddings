// mongosh "$MONGODB_URI" --file mongosh/04-texto-completo.js
// $search usa el índice Lucene con analizador español: ignora tildes/plurales y puntúa con BM25.
const quijote = db.getSiblingDB(process.env.MONGODB_DATABASE || 'quijote');

print('Frase exacta "ínsula Barataria", con resaltado:\n');
quijote.chunks
  .aggregate([
    {
      $search: {
        index: 'chunks_text_index',
        phrase: { query: 'ínsula Barataria', path: 'text' },
        highlight: { path: 'text' },
      },
    },
    { $limit: 3 },
    {
      $project: {
        _id: 0,
        volume: 1,
        chapter: 1,
        score: { $meta: 'searchScore' },
        highlights: { $meta: 'searchHighlights' },
      },
    },
  ])
  .forEach((row) => {
    const snippets = row.highlights
      .flatMap((highlight) => highlight.texts.map((text) => (text.type === 'hit' ? `**${text.value}**` : text.value)).join(''))
      .slice(0, 1);
    print(`vol. ${row.volume}, cap. ${row.chapter}  score=${row.score.toFixed(2)}\n  …${snippets[0]}…\n`);
  });

print('Faceta: en qué capítulos aparece más "Dulcinea" (volumen 2):\n');
quijote.chunks
  .aggregate([
    { $search: { index: 'chunks_text_index', compound: { must: [{ text: { query: 'Dulcinea', path: 'text' } }], filter: [{ equals: { path: 'volume', value: 2 } }] } } },
    { $group: { _id: '$chapter', fragmentos: { $sum: 1 } } },
    { $sort: { fragmentos: -1 } },
    { $limit: 5 },
  ])
  .forEach((row) => printjson(row));
