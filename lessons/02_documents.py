# Lección 02 - El documento con su vector: leerlo, medirlo y mantenerlo (CRUD).
#
# El texto, sus metadatos y su vector viven en el MISMO documento: no hay que sincronizar una base vectorial
# aparte, y los metadatos sirven como filtro en la misma consulta. Si cambia el texto, hay que recalcular su vector.
import bson
import numpy as np
from bson.binary import Binary, BinaryVectorDtype

from lab.client import get_db
from lab.config import EMBEDDING_MODEL
from lab.embeddings import embed_passages
from lab.show import show, step, table, title

db = get_db()
chunks = db.chunks

title("02 - El documento con su vector")

step("Read: un fragmento sin el vector (proyección embedding: 0)")
show(chunks.find_one({"_id": "v1-c008-000"}, {"embedding": 0}))

step("Solapamiento: el último párrafo de un fragmento es el primero del siguiente")
first, second = (chunks.find_one({"_id": _id})["text"].split("\n") for _id in ("v1-c008-000", "v1-c008-001"))
print("último de v1-c008-000: ", first[-1][:90], "…")
print("primero de v1-c008-001:", second[0][:90], "…")

step("Cuánto pesa cada parte del documento ($bsonSize, $strLenBytes, $size)")
table(chunks.aggregate([
    {"$project": {"doc": {"$bsonSize": "$$ROOT"}, "text": {"$strLenBytes": "$text"},
                  "dims": {"$size": "$embedding"}}},
    {"$group": {"_id": None, "documento_bytes": {"$avg": "$doc"}, "texto_bytes": {"$avg": "$text"},
                "dimensiones": {"$first": "$dims"}, "total_MB": {"$sum": "$doc"}}},
    {"$project": {"_id": 0, "dimensiones": 1, "documento_bytes": {"$toInt": "$documento_bytes"},
                  "texto_bytes": {"$toInt": "$texto_bytes"},
                  "total_MB": {"$round": [{"$divide": ["$total_MB", 1048576]}, 1]}}},
]))
print("El vector pesa más que el texto: un array BSON guarda cada número como double de 8 bytes.")

step("Vectores BSON (binData): el mismo vector ocupa menos")
vector = chunks.find_one({"_id": "v1-c008-000"})["embedding"]
table({"formato": name, "bytes": len(bson.encode({"embedding": value}))} for name, value in [
    ("array de doubles", vector),
    ("binData float32", Binary.from_vector(vector, BinaryVectorDtype.FLOAT32)),
    ("binData int8", Binary.from_vector([int(round(x * 127)) for x in vector], BinaryVectorDtype.INT8)),
    ("binData bit (packed)", Binary.from_vector(np.packbits(np.array(vector) > 0).tolist(),
                                                BinaryVectorDtype.PACKED_BIT)),
])
print("El índice vectorial acepta binData; también puede cuantizar por su cuenta (quantization: scalar | binary).")

chunks.delete_many({"_id": "nota-001"})

step("Create: insertar un documento nuevo con su vector")
text = "Don Quijote y Sancho llegan a una venta que el caballero confunde con un castillo."
chunks.insert_one({"_id": "nota-001", "volume": 0, "chapter": 0, "position": 0, "chapter_title": "Nota",
                   "text": text, "embedding": embed_passages([text])[0], "model": EMBEDDING_MODEL})
print("insertado: nota-001")

step("Update: cambiar el texto sin recalcular el vector lo deja desactualizado")
new_text = "Sancho Panza recibe el gobierno de la ínsula Barataria y dicta sentencias sabias."
chunks.update_one({"_id": "nota-001"}, {"$set": {"text": new_text}})
stored = np.array(chunks.find_one({"_id": "nota-001"})["embedding"])
fresh = np.array(embed_passages([new_text])[0])
print(f"similitud(vector guardado, vector del texto nuevo) = {stored @ fresh:.4f}  -> el vector ya no describe el texto")
chunks.update_one({"_id": "nota-001"}, {"$set": {"embedding": fresh.tolist()}})
print("Corregido: el texto y su vector se actualizan juntos, en la misma escritura.")

step("Delete")
print("delete_one:", chunks.delete_one({"_id": "nota-001"}).deleted_count)
