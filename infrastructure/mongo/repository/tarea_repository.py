from typing import Any
from uuid import UUID

from pymongo.collection import Collection

from core.domain.models.tarea import Tarea
from core.domain.ports.tarea_repository import TareaRepository
from infrastructure.mongo.models.tarea import TareaMongo
from infrastructure.mongo.session.client import get_db


class MongoTareaRepository(TareaRepository):
    """
    Implementación de TareaRepository usando MongoDB (Synchronous).
    """

    def __init__(self) -> None:
        self.db = get_db()
        self.collection: Collection[Any] = self.db.tareas

    def save(self, tarea: Tarea) -> None:
        """
        Guarda o actualiza una tarea en la base de datos.

        Argumentos:
            tarea (Tarea): La tarea a guardar.
        """
        tarea_mongo = TareaMongo.from_domain(tarea)
        tarea_dict = tarea_mongo.model_dump(by_alias=True)

        self.collection.update_one(
            {"_id": tarea_dict["_id"]}, {"$set": tarea_dict}, upsert=True
        )

    def get(self, tarea_id: UUID) -> Tarea | None:
        """
        Obtiene una tarea por su ID.

        Argumentos:
            tarea_id (UUID): El ID de la tarea.

        Retorna:
            Tarea | None: La tarea encontrada o None si no existe.
        """
        doc = self.collection.find_one({"_id": str(tarea_id)})
        if not doc:
            return None

        return TareaMongo(**doc).to_domain()

    def list(self) -> list[Tarea]:
        """
        Lista todas las tareas.

        Retorna:
            list[Tarea]: Lista de todas las tareas.
        """
        docs = self.collection.find()
        return [TareaMongo(**doc).to_domain() for doc in docs]

    def eliminar(self, tarea_id: UUID) -> None:
        """
        Elimina una tarea por su ID.

        Argumentos:
            tarea_id (UUID): El ID de la tarea a eliminar.
        """
        self.collection.delete_one({"_id": str(tarea_id)})
