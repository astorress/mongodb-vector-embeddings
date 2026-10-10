# 1. Qué es un embedding

Un **embedding** es una lista de números (un vector) que representa el *significado* de un texto. Un
modelo de lenguaje entrenado para esto pone textos que significan lo mismo en puntos cercanos del
espacio, aunque no compartan palabras:

```text
"don Quijote ataca a unos gigantes"      → [0.021, -0.113, 0.087, …]   ┐ cerca
"arremetió contra los molinos de viento" → [0.019, -0.098, 0.091, …]   ┘
"Sancho cena queso y pan"                → [-0.140, 0.054, -0.012, …]    lejos
```

## Similitud

La cercanía se mide con la **similitud coseno** (el ángulo entre dos vectores): 1 significa misma
dirección, 0 que no tienen relación. Si los vectores están **normalizados** (largo 1), el coseno es
simplemente el producto punto, que es muy barato de calcular. Por eso `rag/embeddings.py` usa
`normalize_embeddings=True`.

MongoDB ofrece tres métricas en el índice vectorial: `cosine`, `dotProduct` (más rápida, exige vectores
normalizados) y `euclidean`.

## El modelo de este proyecto

El modelo se define en `EMBEDDING_MODEL` (`.envs/mongo.env`) y corre **local, en CPU**, con
`sentence-transformers`: no requiere API key ni cuesta dinero. La primera vez se descarga de Hugging
Face y queda en el volumen `vector-embeddings-models`.

Detalles que importan:

- **Dimensiones**: el número de valores del vector. El índice vectorial debe declarar exactamente esa
  cantidad (`numDimensions`). Si cambias de modelo, tienes que recrear los embeddings **y** el índice.
- **Multilingüe**: el libro y las preguntas están en español, así que el modelo tiene que haber sido
  entrenado con español.
- **Prefijos E5**: los modelos de la familia E5 esperan `query: ` delante de las preguntas y
  `passage: ` delante de los textos indexados. Si se omiten, la calidad cae.
- **Ventana**: los modelos tienen un máximo de tokens (512 en E5). Lo que pase de ahí se trunca en
  silencio. Por eso el libro se parte en fragmentos (lección 2).

## Pruébalo

```bash
python - <<'EOF'
import numpy as np
from rag.embeddings import embed_query, embed_passages

frases = ["arremetió contra los molinos de viento", "Sancho cena queso y pan"]
pregunta = np.array(embed_query("don Quijote ataca a unos gigantes"))
for frase, vector in zip(frases, embed_passages(frases)):
    print(f"{pregunta @ np.array(vector):.3f}  {frase}")
EOF
```

Fíjate en que los scores no van de 0 a 1 "bonitos": cada modelo tiene su propio rango. Lo que importa
es el **orden** de los resultados, no el valor absoluto.
