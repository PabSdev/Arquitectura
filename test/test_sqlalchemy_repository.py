import os
import unittest
from uuid import uuid4

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from core.domain.models.tarea import EstadoTarea, Tarea

try:
    from infrastructure.sqlalchemy.session.db import Base, engine
    from infrastructure.sqlalchemy.repository.tarea_repository import SqlAlchemyTareaRepository

    HAS_SQLALCHEMY = True
except ModuleNotFoundError:
    HAS_SQLALCHEMY = False


@unittest.skipUnless(HAS_SQLALCHEMY, "SQLAlchemy no está disponible en este entorno")
class SqlAlchemyTareaRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.repo = SqlAlchemyTareaRepository()

    def test_save_and_get(self) -> None:
        tarea = Tarea(
            id=uuid4(),
            titulo="Tarea SQL",
            descripcion="desc",
            estado=EstadoTarea.EN_PROGRESO,
        )

        self.repo.save(tarea)
        loaded = self.repo.get(tarea.id)

        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded.id, tarea.id)
        self.assertEqual(loaded.titulo, tarea.titulo)
        self.assertEqual(loaded.descripcion, tarea.descripcion)
        self.assertEqual(loaded.estado, tarea.estado)

    def test_eliminar(self) -> None:
        tarea = Tarea(id=uuid4(), titulo="Eliminar SQL")
        self.repo.save(tarea)

        self.repo.eliminar(tarea.id)

        self.assertIsNone(self.repo.get(tarea.id))


if __name__ == "__main__":
    unittest.main()
