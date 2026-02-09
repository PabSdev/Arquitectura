from abc import ABC, abstractmethod
from uuid import UUID

from core.domain.models.tarea import Tarea


class TareaRepository(ABC):
    @abstractmethod
    def list(self) -> list[Tarea]:
        raise NotImplementedError

    @abstractmethod
    def save(self, tarea: Tarea) -> None:
        raise NotImplementedError

    @abstractmethod
    def get(self, tarea_id: UUID) -> Tarea | None:
        raise NotImplementedError

    @abstractmethod
    def eliminar(self, tarea_id: UUID) -> None:
        raise NotImplementedError
