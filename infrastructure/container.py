import os

from core.application.crear_tarea import CrearTareaUseCase
from core.application.editar_tarea import EditarTareaUseCase
from core.application.eliminar_tarea import EliminarTareaUseCase
from core.application.listar_tareas import ListarTareasUseCase
from core.domain.ports.tarea_repository import TareaRepository
from infrastructure.mongo.repository.tarea_repository import MongoTareaRepository
from infrastructure.peewee.repository.tarea_repository import (
    PeeweeTareaRepository,
)
from infrastructure.dual.repository.tarea_repository import DualTareaRepository


def get_tarea_repository() -> TareaRepository:
    orm = os.getenv("ORM", "peewee").lower()

    if orm == "mongo":
        return MongoTareaRepository()
    elif orm == "dual":
        return DualTareaRepository(
            sql_repository=PeeweeTareaRepository(),
            mongo_repository=MongoTareaRepository(),
        )
    # Default to Peewee
    return PeeweeTareaRepository()


def get_crear_tarea_use_case() -> CrearTareaUseCase:
    return CrearTareaUseCase(repository=get_tarea_repository())


def get_editar_tarea_use_case() -> EditarTareaUseCase:
    return EditarTareaUseCase(repository=get_tarea_repository())


def get_eliminar_tarea_use_case() -> EliminarTareaUseCase:
    return EliminarTareaUseCase(repository=get_tarea_repository())


def get_listar_tareas_use_case() -> ListarTareasUseCase:
    return ListarTareasUseCase(repository=get_tarea_repository())
