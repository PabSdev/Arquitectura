import os
import unittest
from uuid import uuid4

# Use memory database for tests
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from core.domain.models.tarea import EstadoTarea, Tarea

try:
    from infrastructure.peewee.session.db import db
    from infrastructure.peewee.model.models import TareaModel
    from infrastructure.peewee.repository.tarea_repository import (
        PeeweeTareaRepository,
    )
    HAS_PEEWEE = True
except ImportError as e:
    print(f"DEBUG: Import failed: {e}")
    HAS_PEEWEE = False

@unittest.skipUnless(HAS_PEEWEE, "Peewee not available")
class PeeweeTareaRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        if not HAS_PEEWEE:
            return
        # Ensure clean state
        if db.is_closed():
            db.connect()
        db.create_tables([TareaModel], safe=True)
        # Clear data
        TareaModel.delete().execute()
        self.repo = PeeweeTareaRepository()

    def tearDown(self) -> None:
        if not HAS_PEEWEE:
            return
        db.drop_tables([TareaModel])
        db.close()

    def test_save_and_get(self) -> None:
        tarea = Tarea(
            id=uuid4(),
            titulo="Tarea Peewee",
            descripcion="desc",
            estado=EstadoTarea.EN_PROGRESO,
        )

        self.repo.save(tarea)
        loaded = self.repo.get(tarea.id)

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.id, tarea.id)
        self.assertEqual(loaded.titulo, tarea.titulo)
        self.assertEqual(loaded.descripcion, tarea.descripcion)
        self.assertEqual(loaded.estado, tarea.estado)

    def test_eliminar(self) -> None:
        tarea = Tarea(id=uuid4(), titulo="Eliminar Peewee")
        self.repo.save(tarea)

        self.repo.eliminar(tarea.id)

        self.assertIsNone(self.repo.get(tarea.id))

if __name__ == "__main__":
    unittest.main()
