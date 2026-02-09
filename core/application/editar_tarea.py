from dataclasses import dataclass
from uuid import UUID

from core.domain.models.tarea import EstadoTarea, Tarea
from core.domain.ports.tarea_repository import TareaRepository


@dataclass(slots=True)
class EditarTareaCommand:
    titulo: str
    descripcion: str | None = None
    estado: EstadoTarea = EstadoTarea.PENDIENTE


class EditarTareaUseCase:
    def __init__(self, repository: TareaRepository) -> None:
        self._repository = repository

    def execute(self, tarea_id: UUID, cmd: EditarTareaCommand) -> Tarea:
        tarea = self._repository.get(tarea_id)
        if tarea is None:
            raise ValueError(f"Tarea con id {tarea_id} no encontrada")

        tarea.titulo = cmd.titulo
        tarea.descripcion = cmd.descripcion
        tarea.estado = cmd.estado

        self._repository.save(tarea)
        return tarea
