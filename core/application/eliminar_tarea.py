from dataclasses import dataclass
from uuid import UUID

from core.domain.ports.tarea_repository import TareaRepository


@dataclass(slots=True)
class EliminarTareaCommand:
    id: UUID


class EliminarTareaUseCase:
    def __init__(self, repository: TareaRepository) -> None:
        self._repository = repository

    def execute(self, cmd: EliminarTareaCommand) -> None:
        tarea = self._repository.get(cmd.id)
        if tarea is None:
            raise ValueError(f"Tarea con id {cmd.id} no encontrada")
        self._repository.eliminar(cmd.id)
