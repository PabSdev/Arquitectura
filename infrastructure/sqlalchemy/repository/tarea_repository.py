from uuid import UUID

from core.domain.models.tarea import EstadoTarea, Tarea
from core.domain.ports.tarea_repository import TareaRepository
from infrastructure.sqlalchemy.session.db import get_session, init_db
from infrastructure.sqlalchemy.model.models import TareaModel


class SqlAlchemyTareaRepository(TareaRepository):
    def __init__(self) -> None:
        init_db()

    def save(self, tarea: Tarea) -> None:
        session = get_session()
        try:
            tarea_model = TareaModel(
                id=str(tarea.id),
                titulo=tarea.titulo,
                descripcion=tarea.descripcion,
                estado=tarea.estado.value,
            )
            session.merge(tarea_model)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get(self, tarea_id: UUID) -> Tarea | None:
        session = get_session()
        try:
            tarea_model = session.get(TareaModel, str(tarea_id))
            if tarea_model is None:
                return None

            return Tarea(
                id=UUID(tarea_model.id),
                titulo=tarea_model.titulo,
                descripcion=tarea_model.descripcion,
                estado=EstadoTarea(tarea_model.estado),
            )
        finally:
            session.close()

    def list(self) -> list[Tarea]:
        session = get_session()
        try:
            tarea_models = session.query(TareaModel).all()
            return [
                Tarea(
                    id=UUID(tarea_model.id),
                    titulo=tarea_model.titulo,
                    descripcion=tarea_model.descripcion,
                    estado=EstadoTarea(tarea_model.estado),
                )
                for tarea_model in tarea_models
            ]
        finally:
            session.close()

    # Compatibilidad temporal con llamadas existentes.
    def listar(self) -> "list[Tarea]":
        return self.list()

    def eliminar(self, tarea_id: UUID) -> None:
        session = get_session()
        try:
            tarea_model = session.get(TareaModel, str(tarea_id))
            if tarea_model is None:
                return
            session.delete(tarea_model)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
