import argparse

from rag.search import SEARCHES, search

# Questions whose answer lives in a known chapter: (question, (volume, chapter))
QUESTIONS = [
    ("¿Por qué don Quijote decide hacerse caballero andante?", (1, 1)),
    ("¿Cómo se llama el caballo de don Quijote y por qué eligió ese nombre?", (1, 1)),
    ("¿Quién arma caballero a don Quijote?", (1, 3)),
    ("¿Qué libros quemaron el cura y el barbero?", (1, 6)),
    ("¿Qué pasó con los molinos de viento?", (1, 8)),
    ("¿Qué le pasa a Sancho cuando lo mantean en la venta?", (1, 17)),
    ("¿Qué vio don Quijote en la cueva de Montesinos?", (2, 23)),
    ("¿Cómo gobierna Sancho la ínsula Barataria?", (2, 45)),
    ("¿Quién es el Caballero de la Blanca Luna y qué le exige a don Quijote?", (2, 64)),
    ("¿Cómo muere don Quijote?", (2, 74)),
]


def main():
    parser = argparse.ArgumentParser(description="Mide hit@1 / hit@k de cada modo de búsqueda.")
    parser.add_argument("-k", type=int, default=5)
    args = parser.parse_args()

    print(f"{'pregunta':<72}" + "".join(f"{mode:>10}" for mode in SEARCHES))
    totals = {mode: [0, 0] for mode in SEARCHES}
    for question, expected in QUESTIONS:
        cells = []
        for mode in SEARCHES:
            found = [(document["volume"], document["chapter"]) for document in search(question, mode, args.k)]
            rank = found.index(expected) + 1 if expected in found else None
            totals[mode][0] += rank == 1
            totals[mode][1] += rank is not None
            cells.append(f"{rank or '-':>10}")
        print(f"{question[:70]:<72}" + "".join(cells))
    print()
    for mode, (hit_1, hit_k) in totals.items():
        print(f"{mode:<10} hit@1={hit_1}/{len(QUESTIONS)}  hit@{args.k}={hit_k}/{len(QUESTIONS)}")


if __name__ == "__main__":
    main()
