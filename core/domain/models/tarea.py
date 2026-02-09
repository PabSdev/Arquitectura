from dataclasses import dataclass
from enum import Enum
from uuid import UUID


class EstadoTarea(Enum):
    PENDIENTE = "pendiente"
    EN_PROGRESO = "en_progreso"
    COMPLETADA = "completada"


@dataclass(slots=True)
class Tarea:
    id: UUID
    titulo: str
    descripcion: str | None = None
    estado: EstadoTarea = EstadoTarea.PENDIENTE
