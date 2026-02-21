from uuid import UUID
from typing import List
from core.domain.models.tarea import Tarea, EstadoTarea
from core.domain.ports.tarea_repository import TareaRepository
from infrastructure.peewee.model.models import TareaModel
from infrastructure.peewee.session.db import db

class PeeweeTareaRepository(TareaRepository):
    def __init__(self):
        # Ensure tables exist. In a real production app, this might be handled by migrations.
        # But for this setup, we do it on init like the SQLAlchemy repo did.
        db.connect(reuse_if_open=True)
        db.create_tables([TareaModel], safe=True)

    def save(self, tarea: Tarea) -> None:
        with db.atomic():
            try:
                existing = TareaModel.get(TareaModel.id == tarea.id)
                existing.titulo = tarea.titulo
                existing.descripcion = tarea.descripcion
                existing.estado = tarea.estado.value
                existing.save()
            except TareaModel.DoesNotExist:
                TareaModel.create(
                    id=tarea.id,
                    titulo=tarea.titulo,
                    descripcion=tarea.descripcion,
                    estado=tarea.estado.value
                )

    def get(self, tarea_id: UUID) -> Tarea | None:
        try:
            tarea_model = TareaModel.get(TareaModel.id == tarea_id)
            return Tarea(
                id=tarea_model.id,
                titulo=tarea_model.titulo,
                descripcion=tarea_model.descripcion,
                estado=EstadoTarea(tarea_model.estado)
            )
        except TareaModel.DoesNotExist:
            return None

    def list(self) -> List[Tarea]:
        return [
            Tarea(
                id=t.id,
                titulo=t.titulo,
                descripcion=t.descripcion,
                estado=EstadoTarea(t.estado)
            )
            for t in TareaModel.select()
        ]

    def listar(self) -> List[Tarea]:
        return self.list()

    def eliminar(self, tarea_id: UUID) -> None:
        query = TareaModel.delete().where(TareaModel.id == tarea_id)
        query.execute()
