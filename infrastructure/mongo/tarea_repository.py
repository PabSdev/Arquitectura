from uuid import UUID

from core.domain.models.tarea import Tarea
from core.domain.ports.tarea_repository import TareaRepository


class MongoTareaRepository(TareaRepository):
    def list(self) -> list[Tarea]:
        # Placeholder: aquí iría find.
        return []

    def save(self, tarea: Tarea) -> None:
        # Placeholder: aquí iría insert_one.
        return None

    def get(self, tarea_id: UUID) -> Tarea | None:
        # Placeholder: aquí iría find_one.
        return None

    def eliminar(self, tarea_id: UUID) -> None:
        # Placeholder: aquí iría delete_one.
        return None
