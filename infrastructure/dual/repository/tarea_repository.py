from uuid import UUID
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Any
import os
# ── Imports a nivel de módulo (Patrón 10: evitar overhead de import repetido) ──
import psycopg2
from pymongo import MongoClient

from core.domain.models.tarea import Tarea
from core.domain.ports.tarea_repository import TareaRepository
from infrastructure.sqlalchemy.repository.tarea_repository import (
    SqlAlchemyTareaRepository,
)
from infrastructure.mongo.repository.tarea_repository import MongoTareaRepository

logger = logging.getLogger(__name__)

# ── Pool de threads compartido (Patrón 14: reutilizar pool, no crear por llamada) ──
# max_workers=4: 2 para pings + 2 para operaciones reales en paralelo
executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="DualRepo")

# ── Configuración de conexión (variables locales en módulo → acceso más rápido) ──
_POSTGRES_DSN = os.getenv("DATABASE_URL")
_MONGO_DSN = os.getenv("MONGO_URI")
_PING_TIMEOUT_SECS = 3
_PING_TIMEOUT_MS = _PING_TIMEOUT_SECS * 1000


def _ping_postgres() -> bool:
    """
    Hace ping a PostgreSQL con timeout controlado.

    Returns:
        True si la BDD está disponible, False en caso contrario.
    """
    try:
        # psycopg2: connect_timeout es un kwarg separado, no parte del DSN
        conn = psycopg2.connect(dsn=_POSTGRES_DSN, connect_timeout=_PING_TIMEOUT_SECS)
        conn.close()
        return True
    except Exception as e:
        logger.error(f"🔴 Postgres no disponible: {e}")
        return False


def _ping_mongo() -> bool:
    """
    Hace ping a MongoDB con timeout controlado.

    Returns:
        True si la BDD está disponible, False en caso contrario.
    """
    try:
        client = MongoClient(_MONGO_DSN, serverSelectionTimeoutMS=_PING_TIMEOUT_MS)
        client.admin.command("ping")
        client.close()
        return True
    except Exception as e:
        logger.error(f"🔴 Mongo no disponible: {e}")
        return False


def _ping_ambas_bdd() -> tuple[bool, bool]:
    """
    Ejecuta los pings a PostgreSQL y MongoDB EN PARALELO.
    Latencia total = max(ping_sql, ping_mongo), no la suma.

    Returns:
        Tupla (postgres_ok, mongo_ok)
    """
    future_sql = executor.submit(_ping_postgres)
    future_mongo = executor.submit(_ping_mongo)
    # Esperamos ambos resultados (timeout máximo = _PING_TIMEOUT_SECS + margen)
    postgres_ok = future_sql.result(timeout=_PING_TIMEOUT_SECS + 1)
    mongo_ok = future_mongo.result(timeout=_PING_TIMEOUT_SECS + 1)
    return postgres_ok, mongo_ok


class DualTareaRepository(TareaRepository):
    """
    Repositorio Dual que escribe y lee desde SQLAlchemy y MongoDB simultáneamente.

    Estrategia de Migración (según roadmap.md):
    - ESCRITURA (save/eliminar): Ping previo en paralelo a ambas BDD.
      Si ambas responden → escribe en paralelo.
      Si solo una responde → avisa y escribe solo en la disponible.
      Si ninguna responde → falla inmediatamente sin intentar escribir.
    - LECTURA (get/list): Lee de SQLAlchemy por defecto, con fallback a MongoDB.
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

    # ──────────────────────────────────────────────────────────────────────────
    # Métodos privados de infraestructura
    # ──────────────────────────────────────────────────────────────────────────

    def _execute_parallel(
        self, sql_func: Callable[[], Any], mongo_func: Callable[[], Any]
    ) -> tuple[Any | None, Exception | None, Any | None, Exception | None]:
        """
        Ejecuta dos operaciones en paralelo usando el ThreadPoolExecutor compartido.

        Args:
            sql_func: Función a ejecutar en SQLAlchemy
            mongo_func: Función a ejecutar en MongoDB

        Returns:
            Tupla (sql_result, sql_error, mongo_result, mongo_error)
        """
        sql_result, sql_error = None, None
        mongo_result, mongo_error = None, None

        future_sql = executor.submit(sql_func)
        future_mongo = executor.submit(mongo_func)

        # Recolectar resultados a medida que se completan (sin bloqueo total)
        for future in as_completed([future_sql, future_mongo]):
            try:
                result = future.result()
                if future is future_sql:
                    sql_result = result
                    logger.debug("✓ Operación SQLAlchemy completada")
                else:
                    mongo_result = result
                    logger.debug("✓ Operación MongoDB completada")
            except Exception as e:
                if future is future_sql:
                    sql_error = e
                    logger.error(f"✗ SQLAlchemy falló: {e}")
                else:
                    mongo_error = e
                    logger.error(f"✗ MongoDB falló: {e}")

        return sql_result, sql_error, mongo_result, mongo_error

    def _execute_solo_sql(self, sql_func: Callable[[], Any]) -> None:
        """Ejecuta la operación únicamente en SQLAlchemy."""
        try:
            sql_func()
            logger.debug("✓ Operación SQLAlchemy (solo) completada")
        except Exception as e:
            logger.error(f"✗ SQLAlchemy (solo) falló: {e}")
            raise

    def _execute_solo_mongo(self, mongo_func: Callable[[], Any]) -> None:
        """Ejecuta la operación únicamente en MongoDB."""
        try:
            mongo_func()
            logger.debug("✓ Operación MongoDB (solo) completada")
        except Exception as e:
            logger.error(f"✗ MongoDB (solo) falló: {e}")
            raise

    def _dispatch_escritura(
        self,
        operacion: str,
        sql_func: Callable[[], Any],
        mongo_func: Callable[[], Any],
        entidad_id: Any,
    ) -> None:
        """
        Orquesta una operación de escritura con ping previo.

        1. Hace ping en paralelo a ambas BDD.
        2. Según disponibilidad, despacha la operación.

        Args:
            operacion:  Nombre de la operación para logs ('save', 'eliminar', etc.)
            sql_func:   Función a ejecutar en SQLAlchemy
            mongo_func: Función a ejecutar en MongoDB
            entidad_id: ID de la entidad (solo para logs)
        """
        logger.info(f"🏓 Ping previo a BDD para {operacion} de {entidad_id}...")
        postgres_ok, mongo_ok = _ping_ambas_bdd()

        # ── Ambas BDD caídas → falla rápida ──────────────────────────────────
        if not postgres_ok and not mongo_ok:
            msg = (
                f"❌ {operacion} abortado: ninguna BDD disponible "
                f"(Postgres={postgres_ok}, Mongo={mongo_ok})"
            )
            logger.error(msg)
            raise Exception(msg)

        # ── Solo Postgres disponible ──────────────────────────────────────────
        if postgres_ok and not mongo_ok:
            logger.warning(
                f"⚠️ MongoDB no disponible. {operacion} de {entidad_id} "
                f"se guardará SOLO en Postgres."
            )
            self._execute_solo_sql(sql_func)
            return

        # ── Solo MongoDB disponible ───────────────────────────────────────────
        if mongo_ok and not postgres_ok:
            logger.warning(
                f"⚠️ Postgres no disponible. {operacion} de {entidad_id} "
                f"se guardará SOLO en MongoDB."
            )
            self._execute_solo_mongo(mongo_func)
            return

        # ── Ambas disponibles → escritura dual en paralelo ───────────────────
        logger.info(f"🔄 {operacion} dual iniciado para {entidad_id}")
        _, sql_error, _, mongo_error = self._execute_parallel(sql_func, mongo_func)

        if sql_error and mongo_error:
            error_msg = (
                f"{operacion} falló en ambas bases de datos. "
                f"SQLAlchemy: {sql_error}. MongoDB: {mongo_error}"
            )
            logger.error(f"❌ {error_msg}")
            raise Exception(error_msg)

        if sql_error:
            logger.warning(f"⚠️ SQLAlchemy falló pero MongoDB tuvo éxito en {operacion} {entidad_id}")
        elif mongo_error:
            logger.warning(f"⚠️ MongoDB falló pero SQLAlchemy tuvo éxito en {operacion} {entidad_id}")
        else:
            logger.info(f"✅ {operacion} dual exitoso para {entidad_id}")

    # ──────────────────────────────────────────────────────────────────────────
    # Interfaz pública
    # ──────────────────────────────────────────────────────────────────────────

    def save(self, tarea: Tarea) -> None:
        """
        Guarda la tarea con ping previo a ambas BDD.

        - Si ambas responden: escritura en paralelo.
        - Si solo una responde: guarda solo en la disponible + warning.
        - Si ninguna responde: lanza excepción inmediata.

        Args:
            tarea: La tarea a guardar.

        Raises:
            Exception: Si ninguna BDD está disponible, o si la escritura falla en ambas.
        """
        self._dispatch_escritura(
            operacion="save",
            sql_func=lambda: self._sql_repo.save(tarea),
            mongo_func=lambda: self._mongo_repo.save(tarea),
            entidad_id=tarea.id,
        )

    def get(self, tarea_id: UUID) -> Tarea | None:
        """
        Obtiene una tarea, intentando SQLAlchemy primero, luego MongoDB (Dual-Read).

        No hace ping previo: la lectura es tolerante a fallos por diseño.

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

        No hace ping previo: la lectura es tolerante a fallos por diseño.

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
        Elimina una tarea con ping previo a ambas BDD.

        - Si ambas responden: eliminación en paralelo.
        - Si solo una responde: elimina solo en la disponible + warning.
        - Si ninguna responde: lanza excepción inmediata.

        Args:
            tarea_id: El ID de la tarea a eliminar.

        Raises:
            Exception: Si ninguna BDD está disponible, o si la eliminación falla en ambas.
        """
        self._dispatch_escritura(
            operacion="eliminar",
            sql_func=lambda: self._sql_repo.eliminar(tarea_id),
            mongo_func=lambda: self._mongo_repo.eliminar(tarea_id),
            entidad_id=tarea_id,
        )
