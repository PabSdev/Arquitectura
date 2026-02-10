from uuid import UUID
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Any

from core.domain.models.tarea import Tarea
from core.domain.ports.tarea_repository import TareaRepository
from infrastructure.sqlalchemy.repository.tarea_repository import (
    SqlAlchemyTareaRepository,
)
from infrastructure.mongo.repository.tarea_repository import MongoTareaRepository

logger = logging.getLogger(__name__)

# Pool de threads para ejecutar operaciones en paralelo
executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="DualRepo")


class DualTareaRepository(TareaRepository):
    """
    Repositorio Dual que escribe y lee desde SQLAlchemy y MongoDB simultáneamente.

    Estrategia de Migración (según roadmap.md):
    - ESCRITURA (save/eliminar): Se ejecuta en AMBAS bases de datos EN PARALELO.
    - LECTURA (get/list): Lee de SQLAlchemy por defecto, con fallback a MongoDB.

    Esto permite una migración gradual sin downtime.
    """

    def __init__(
        self,
        sql_repository: SqlAlchemyTareaRepository | None = None,
        mongo_repository: MongoTareaRepository | None = None,
    ) -> None:
        """
        Inicializa el repositorio dual.

        Args:
            sql_repository: Repositorio SQLAlchemy. Si es None, se instancia automáticamente.
            mongo_repository: Repositorio MongoDB. Si es None, se instancia automáticamente.
        """
        self._sql_repo = sql_repository or SqlAlchemyTareaRepository()
        self._mongo_repo = mongo_repository or MongoTareaRepository()
        logger.info("DualTareaRepository inicializado con SQLAlchemy y MongoDB")

    def _execute_parallel(
        self, sql_func: Callable[[], Any], mongo_func: Callable[[], Any]
    ) -> tuple[Any | None, Exception | None, Any | None, Exception | None]:
        """
        Ejecuta dos operaciones en paralelo usando ThreadPoolExecutor.

        Args:
            sql_func: Función a ejecutar en SQLAlchemy
            mongo_func: Función a ejecutar en MongoDB

        Returns:
            Tupla (sql_result, sql_error, mongo_result, mongo_error)
        """
        sql_result, sql_error = None, None
        mongo_result, mongo_error = None, None

        # Submit ambas tareas al executor
        future_sql = executor.submit(sql_func)
        future_mongo = executor.submit(mongo_func)

        # Recolectar resultados a medida que se completan
        for future in as_completed([future_sql, future_mongo]):
            try:
                result = future.result()
                if future == future_sql:
                    sql_result = result
                    logger.debug("✓ Operación SQLAlchemy completada")
                else:
                    mongo_result = result
                    logger.debug("✓ Operación MongoDB completada")
            except Exception as e:
                if future == future_sql:
                    sql_error = e
                    logger.error(f"✗ SQLAlchemy falló: {e}")
                else:
                    mongo_error = e
                    logger.error(f"✗ MongoDB falló: {e}")

        return sql_result, sql_error, mongo_result, mongo_error

    def save(self, tarea: Tarea) -> None:
        """
        Guarda la tarea en ambas bases de datos EN PARALELO (Dual-Write).

        Args:
            tarea: La tarea a guardar.

        Raises:
            Exception: Si falla la escritura en ambas bases de datos.
        """
        logger.info(f"🔄 Dual-Write iniciado para tarea {tarea.id}")

        # Ejecutar ambas operaciones en paralelo
        _, sql_error, _, mongo_error = self._execute_parallel(
            lambda: self._sql_repo.save(tarea),
            lambda: self._mongo_repo.save(tarea),
        )

        # Si ambas fallaron, lanzar excepción
        if sql_error and mongo_error:
            error_msg = (
                f"Dual-Write falló en ambas bases de datos. "
                f"SQLAlchemy: {sql_error}. MongoDB: {mongo_error}"
            )
            logger.error(f"❌ {error_msg}")
            raise Exception(error_msg)

        # Log de advertencia si solo una falló
        if sql_error:
            logger.warning(f"⚠️ SQLAlchemy falló pero MongoDB tuvo éxito para tarea {tarea.id}")
        elif mongo_error:
            logger.warning(f"⚠️ MongoDB falló pero SQLAlchemy tuvo éxito para tarea {tarea.id}")
        else:
            logger.info(f"✅ Dual-Write exitoso para tarea {tarea.id}")

    def get(self, tarea_id: UUID) -> Tarea | None:
        """
        Obtiene una tarea, intentando SQLAlchemy primero, luego MongoDB (Dual-Read).

        Args:
            tarea_id: El ID de la tarea.

        Returns:
            La tarea si existe, None en caso contrario.
        """
        logger.debug(f"🔍 Buscando tarea {tarea_id}")

        # Intenta leer de SQLAlchemy primero (base de datos "principal")
        try:
            tarea = self._sql_repo.get(tarea_id)
            if tarea is not None:
                logger.debug(f"✓ Tarea {tarea_id} obtenida de SQLAlchemy")
                return tarea
        except Exception as e:
            logger.warning(f"⚠️ Error obteniendo de SQLAlchemy: {e}")

        # Fallback a MongoDB si SQLAlchemy falló o no encontró el registro
        try:
            tarea = self._mongo_repo.get(tarea_id)
            if tarea is not None:
                logger.info(f"✓ Tarea {tarea_id} obtenida de MongoDB (fallback)")
                return tarea
        except Exception as e:
            logger.warning(f"⚠️ Error obteniendo de MongoDB: {e}")

        logger.debug(f"❌ Tarea {tarea_id} no encontrada en ninguna base de datos")
        return None

    def list(self) -> list[Tarea]:
        """
        Lista todas las tareas desde SQLAlchemy (base de datos "principal").
        Con fallback a MongoDB si falla.

        Returns:
            Lista de todas las tareas.
        """
        logger.debug("📋 Listando todas las tareas")

        try:
            tareas = self._sql_repo.list()
            logger.debug(f"✓ Listadas {len(tareas)} tareas de SQLAlchemy")
            return tareas
        except Exception as e:
            logger.warning(f"⚠️ Error listando de SQLAlchemy: {e}, intentando MongoDB")

            # Fallback a MongoDB
            try:
                tareas = self._mongo_repo.list()
                logger.info(f"✓ Listadas {len(tareas)} tareas de MongoDB (fallback)")
                return tareas
            except Exception as mongo_error:
                logger.error(f"❌ Error listando de MongoDB: {mongo_error}")
                raise Exception(
                    f"Falló el listado en ambas bases de datos. "
                    f"SQLAlchemy: {e}. MongoDB: {mongo_error}"
                )

    def eliminar(self, tarea_id: UUID) -> None:
        """
        Elimina una tarea de ambas bases de datos EN PARALELO (Dual-Delete).

        Args:
            tarea_id: El ID de la tarea a eliminar.

        Raises:
            Exception: Si falla la eliminación en ambas bases de datos.
        """
        logger.info(f"🗑️ Dual-Delete iniciado para tarea {tarea_id}")

        # Ejecutar ambas operaciones de eliminación en paralelo
        _, sql_error, _, mongo_error = self._execute_parallel(
            lambda: self._sql_repo.eliminar(tarea_id),
            lambda: self._mongo_repo.eliminar(tarea_id),
        )

        # Si ambas fallaron, lanzar excepción
        if sql_error and mongo_error:
            error_msg = (
                f"Dual-Delete falló en ambas bases de datos. "
                f"SQLAlchemy: {sql_error}. MongoDB: {mongo_error}"
            )
            logger.error(f"❌ {error_msg}")
            raise Exception(error_msg)

        # Log de advertencia si solo una falló
        if sql_error:
            logger.warning(
                f"⚠️ SQLAlchemy falló pero MongoDB eliminó tarea {tarea_id}"
            )
        elif mongo_error:
            logger.warning(
                f"⚠️ MongoDB falló pero SQLAlchemy eliminó tarea {tarea_id}"
            )
        else:
            logger.info(f"✅ Dual-Delete exitoso para tarea {tarea_id}")

