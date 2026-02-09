from dataclasses import dataclass
from uuid import uuid4

from core.domain.models.tarea import EstadoTarea, Tarea
from core.domain.ports.tarea_repository import TareaRepository


@dataclass(slots=True)
class CrearTareaCommand:
    titulo: str
    descripcion: str | None = None
    estado: EstadoTarea = EstadoTarea.PENDIENTE


class CrearTareaUseCase:
    def __init__(self, repository: TareaRepository) -> None:
        self._repository = repository

    def execute(self, cmd: CrearTareaCommand) -> Tarea:
        tarea = Tarea(
            id=uuid4(),
            titulo=cmd.titulo,
            descripcion=cmd.descripcion,
            estado=cmd.estado,
        )
        self._repository.save(tarea)
        return tarea
