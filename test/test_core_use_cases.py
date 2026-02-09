import unittest
from uuid import UUID, uuid4

from core.application.crear_tarea import CrearTareaCommand, CrearTareaUseCase
from core.application.editar_tarea import EditarTareaCommand, EditarTareaUseCase
from core.application.eliminar_tarea import EliminarTareaCommand, EliminarTareaUseCase
from core.domain.models.tarea import EstadoTarea, Tarea
from core.domain.ports.tarea_repository import TareaRepository


class InMemoryTareaRepository(TareaRepository):
    def __init__(self) -> None:
        self._data: dict[UUID, Tarea] = {}

    def list(self) -> list[Tarea]:
        return list(self._data.values())

    def save(self, tarea: Tarea) -> None:
        self._data[tarea.id] = tarea

    def get(self, tarea_id: UUID) -> Tarea | None:
        return self._data.get(tarea_id)

    def eliminar(self, tarea_id: UUID) -> None:
        self._data.pop(tarea_id, None)


class CoreUseCasesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = InMemoryTareaRepository()

    def test_crear_tarea_genera_id_uuid_y_guarda(self) -> None:
        use_case = CrearTareaUseCase(self.repo)

        tarea = use_case.execute(
            CrearTareaCommand(
                titulo="Diseñar arquitectura",
                descripcion="Hexagonal",
                estado=EstadoTarea.EN_PROGRESO,
            )
        )

        self.assertIsInstance(tarea.id, UUID)
        self.assertEqual(tarea.estado, EstadoTarea.EN_PROGRESO)
        self.assertEqual(self.repo.get(tarea.id), tarea)

    def test_editar_tarea_actualiza_y_persiste(self) -> None:
        tarea_id = uuid4()
        original = Tarea(id=tarea_id, titulo="Inicial", descripcion="d1")
        self.repo.save(original)

        use_case = EditarTareaUseCase(self.repo)
        updated = use_case.execute(
            tarea_id,
            EditarTareaCommand(
                titulo="Actualizada",
                descripcion="d2",
                estado=EstadoTarea.COMPLETADA,
            ),
        )

        self.assertEqual(updated.id, tarea_id)
        self.assertEqual(updated.titulo, "Actualizada")
        self.assertEqual(updated.descripcion, "d2")
        self.assertEqual(updated.estado, EstadoTarea.COMPLETADA)
        self.assertEqual(self.repo.get(tarea_id), updated)

    def test_editar_tarea_inexistente_lanza_error(self) -> None:
        use_case = EditarTareaUseCase(self.repo)

        with self.assertRaises(ValueError):
            use_case.execute(
                uuid4(),
                EditarTareaCommand(titulo="x", descripcion="y"),
            )

    def test_eliminar_tarea_borra_registro(self) -> None:
        tarea_id = uuid4()
        self.repo.save(Tarea(id=tarea_id, titulo="Eliminar"))

        use_case = EliminarTareaUseCase(self.repo)
        use_case.execute(EliminarTareaCommand(id=tarea_id))

        self.assertIsNone(self.repo.get(tarea_id))

    def test_eliminar_tarea_inexistente_lanza_error(self) -> None:
        use_case = EliminarTareaUseCase(self.repo)

        with self.assertRaises(ValueError):
            use_case.execute(EliminarTareaCommand(id=uuid4()))


if __name__ == "__main__":
    unittest.main()
