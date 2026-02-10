from dataclasses import dataclass

from core.domain.models.tarea import Tarea


@dataclass(slots=True)
class ListarTareasCommand:
    pass


class ListarTareasUseCase:
    def __init__(self, repository) -> None:
        self._repository = repository

    def execute(self) -> list[Tarea]:
        return self._repository.list()
