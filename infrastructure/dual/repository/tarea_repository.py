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
from infrastructure.peewee.repository.tarea_repository import (
    PeeweeTareaRepository,
)
from infrastructure.mongo.repository.tarea_repository import MongoTareaRepository
from infrastructure.dual.circuit_breaker import CircuitBreaker
from infrastructure.dual.retry import retry_with_backoff

logger = logging.getLogger(__name__)

# ── Pool de threads compartido (Patrón 14: reutilizar pool, no crear por llamada) ──
# max_workers=4: 2 para pings + 2 para operaciones reales en paralelo
executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="DualRepo")

# ── Configuración de conexión (variables locales en módulo → acceso más rápido) ──
_SQL_DSN = os.getenv("DATABASE_URL")
_MONGO_DSN = os.getenv("MONGO_URI")
_PING_TIMEOUT_SECS = 3
_PING_TIMEOUT_MS = _PING_TIMEOUT_SECS * 1000

# ── Configuración de resiliencia ──────────────────────────────────────────────
_CIRCUIT_FAILURE_THRESHOLD = 3    # Fallos consecutivos para abrir circuito
_CIRCUIT_RECOVERY_TIMEOUT = 30.0  # Segundos antes de probar reconexión
_RETRY_MAX_RETRIES = 2            # Reintentos por operación
_RETRY_BASE_DELAY = 0.5           # Delay base (se duplica por retry)
_PARALLEL_TIMEOUT = 10.0          # Timeout para operaciones paralelas


def _ping_sql() -> bool:
    """
    Hace ping a la base de datos SQL (Postgres o SQLite).

    Returns:
        True si la BDD está disponible, False en caso contrario.
    """
    # Si es SQLite, asumimos que está disponible (es un archivo local o memoria)
    if not _SQL_DSN or _SQL_DSN.startswith("sqlite"):
        return True

    try:
        # Intento con psycopg2 si es Postgres
        if "postgres" in _SQL_DSN:
            conn = psycopg2.connect(dsn=_SQL_DSN, connect_timeout=_PING_TIMEOUT_SECS)
            conn.close()
            return True
        return True
    except Exception as e:
        logger.error(f"🔴 SQL no disponible: {e}")
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
    Ejecuta los pings a SQL y MongoDB EN PARALELO.
    Latencia total = max(ping_sql, ping_mongo), no la suma.

    Returns:
        Tupla (sql_ok, mongo_ok)
    """
    future_sql = executor.submit(_ping_sql)
    future_mongo = executor.submit(_ping_mongo)
    # Esperamos ambos resultados (timeout máximo = _PING_TIMEOUT_SECS + margen)
    sql_ok = future_sql.result(timeout=_PING_TIMEOUT_SECS + 1)
    mongo_ok = future_mongo.result(timeout=_PING_TIMEOUT_SECS + 1)
    return sql_ok, mongo_ok


class DualTareaRepository(TareaRepository):
    """
    Repositorio Dual que escribe y lee desde Peewee (SQL) y MongoDB simultáneamente.

    Mejoras de resiliencia:
    - Circuit Breaker: evita golpear una BDD que sabemos que está caída.
    - Retry con Backoff: reintenta errores transitorios antes de ir al fallback.
    - Timeout explícito en operaciones paralelas.

    Estrategia de Migración (según roadmap.md):
    - ESCRITURA (save/eliminar): Ping previo en paralelo a ambas BDD.
      Si ambas responden → escribe en paralelo.
      Si solo una responde → avisa y escribe solo en la disponible.
      Si ninguna responde → falla inmediatamente sin intentar escribir.
    - LECTURA (get/list): Lee de SQL (Peewee) por defecto, con fallback a MongoDB.
      Circuit Breaker puede saltar SQL directo si está en estado OPEN.
    """

    def __init__(
        self,
        sql_repository: PeeweeTareaRepository | None = None,
        mongo_repository: MongoTareaRepository | None = None,
    ) -> None:
        """
        Inicializa el repositorio dual con Circuit Breakers independientes.

        Args:
            sql_repository: Repositorio Peewee. Si es None, se instancia automáticamente.
            mongo_repository: Repositorio MongoDB. Si es None, se instancia automáticamente.
        """
        self._sql_repo = sql_repository or PeeweeTareaRepository()
        self._mongo_repo = mongo_repository or MongoTareaRepository()

        # ── Circuit Breakers independientes por BDD ──
        self._sql_circuit = CircuitBreaker(
            name="Peewee",
            failure_threshold=_CIRCUIT_FAILURE_THRESHOLD,
            recovery_timeout=_CIRCUIT_RECOVERY_TIMEOUT,
        )
        self._mongo_circuit = CircuitBreaker(
            name="MongoDB",
            failure_threshold=_CIRCUIT_FAILURE_THRESHOLD,
            recovery_timeout=_CIRCUIT_RECOVERY_TIMEOUT,
        )

        logger.info(
            "DualTareaRepository inicializado con Peewee y MongoDB "
            "(Circuit Breaker + Retry habilitados)"
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Métodos privados de infraestructura
    # ──────────────────────────────────────────────────────────────────────────

    def _execute_parallel(
        self, sql_func: Callable[[], Any], mongo_func: Callable[[], Any]
    ) -> tuple[Any | None, Exception | None, Any | None, Exception | None]:
        """
        Ejecuta dos operaciones en paralelo usando el ThreadPoolExecutor compartido.
        Incluye timeout explícito para evitar bloqueos indefinidos.

        Args:
            sql_func: Función a ejecutar en Peewee
            mongo_func: Función a ejecutar en MongoDB

        Returns:
            Tupla (sql_result, sql_error, mongo_result, mongo_error)
        """
        sql_result, sql_error = None, None
        mongo_result, mongo_error = None, None

        future_sql = executor.submit(sql_func)
        future_mongo = executor.submit(mongo_func)

        # Recolectar resultados con timeout explícito (Mejora 3)
        try:
            for future in as_completed(
                [future_sql, future_mongo], timeout=_PARALLEL_TIMEOUT
            ):
                try:
                    result = future.result()
                    if future is future_sql:
                        sql_result = result
                        self._sql_circuit.record_success()
                        logger.debug("✓ Operación Peewee completada")
                    else:
                        mongo_result = result
                        self._mongo_circuit.record_success()
                        logger.debug("✓ Operación MongoDB completada")
                except Exception as e:
                    if future is future_sql:
                        sql_error = e
                        self._sql_circuit.record_failure()
                        logger.error(f"✗ Peewee falló: {e}")
                    else:
                        mongo_error = e
                        self._mongo_circuit.record_failure()
                        logger.error(f"✗ MongoDB falló: {e}")
        except TimeoutError:
            # as_completed timeout — marcar como error las que no terminaron
            if not future_sql.done():
                sql_error = TimeoutError("Peewee excedió timeout paralelo")
                self._sql_circuit.record_failure()
                logger.error(f"⏰ Peewee timeout ({_PARALLEL_TIMEOUT}s)")
                future_sql.cancel()
            if not future_mongo.done():
                mongo_error = TimeoutError("MongoDB excedió timeout paralelo")
                self._mongo_circuit.record_failure()
                logger.error(f"⏰ MongoDB timeout ({_PARALLEL_TIMEOUT}s)")
                future_mongo.cancel()

        return sql_result, sql_error, mongo_result, mongo_error

    def _execute_solo_sql(self, sql_func: Callable[[], Any]) -> None:
        """Ejecuta la operación únicamente en Peewee con retry."""
        try:
            retry_with_backoff(
                sql_func,
                max_retries=_RETRY_MAX_RETRIES,
                base_delay=_RETRY_BASE_DELAY,
            )
            self._sql_circuit.record_success()
            logger.debug("✓ Operación Peewee (solo) completada")
        except Exception as e:
            self._sql_circuit.record_failure()
            logger.error(f"✗ Peewee (solo) falló: {e}")
            raise

    def _execute_solo_mongo(self, mongo_func: Callable[[], Any]) -> None:
        """Ejecuta la operación únicamente en MongoDB con retry."""
        try:
            retry_with_backoff(
                mongo_func,
                max_retries=_RETRY_MAX_RETRIES,
                base_delay=_RETRY_BASE_DELAY,
            )
            self._mongo_circuit.record_success()
            logger.debug("✓ Operación MongoDB (solo) completada")
        except Exception as e:
            self._mongo_circuit.record_failure()
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

        1. Consulta Circuit Breakers.
        2. Si algún circuito está OPEN, solo escribe en la BDD disponible.
        3. Si ambos están CLOSED/HALF_OPEN, hace ping en paralelo y despacha.

        Args:
            operacion:  Nombre de la operación para logs ('save', 'eliminar', etc.)
            sql_func:   Función a ejecutar en SQLAlchemy
            mongo_func: Función a ejecutar en MongoDB
            entidad_id: ID de la entidad (solo para logs)
        """
        sql_allowed = self._sql_circuit.allow_request()
        mongo_allowed = self._mongo_circuit.allow_request()

        # ── Ambos circuitos abiertos → comprobar con ping ─────────────────────
        if not sql_allowed and not mongo_allowed:
            logger.error(
                f"❌ {operacion} abortado: ambos Circuit Breakers abiertos "
                f"(SQL={self._sql_circuit.state}, Mongo={self._mongo_circuit.state})"
            )
            raise Exception(
                f"{operacion} abortado: ninguna BDD disponible "
                f"(ambos Circuit Breakers en estado OPEN)"
            )

        # ── Solo un circuito disponible → escritura directa ───────────────────
        if sql_allowed and not mongo_allowed:
            logger.warning(
                f"⚡ MongoDB circuit OPEN. {operacion} de {entidad_id} "
                f"se guardará SOLO en Peewee."
            )
            self._execute_solo_sql(sql_func)
            return

        if mongo_allowed and not sql_allowed:
            logger.warning(
                f"⚡ Peewee circuit OPEN. {operacion} de {entidad_id} "
                f"se guardará SOLO en MongoDB."
            )
            self._execute_solo_mongo(mongo_func)
            return

        # ── Ambos circuitos permiten → ping previo para confirmar ─────────────
        logger.info(f"🏓 Ping previo a BDD para {operacion} de {entidad_id}...")
        sql_ok, mongo_ok = _ping_ambas_bdd()

        # ── Ambas BDD caídas → falla rápida ──────────────────────────────────
        if not sql_ok and not mongo_ok:
            self._sql_circuit.record_failure()
            self._mongo_circuit.record_failure()
            msg = (
                f"❌ {operacion} abortado: ninguna BDD disponible "
                f"(SQL={sql_ok}, Mongo={mongo_ok})"
            )
            logger.error(msg)
            raise Exception(msg)

        # ── Solo SQL disponible ──────────────────────────────────────────
        if sql_ok and not mongo_ok:
            self._mongo_circuit.record_failure()
            logger.warning(
                f"⚠️ MongoDB no disponible. {operacion} de {entidad_id} "
                f"se guardará SOLO en SQL."
            )
            self._execute_solo_sql(sql_func)
            return

        # ── Solo MongoDB disponible ───────────────────────────────────────────
        if mongo_ok and not sql_ok:
            self._sql_circuit.record_failure()
            logger.warning(
                f"⚠️ SQL no disponible. {operacion} de {entidad_id} "
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
                f"Peewee: {sql_error}. MongoDB: {mongo_error}"
            )
            logger.error(f"❌ {error_msg}")
            raise Exception(error_msg)

        if sql_error:
            logger.warning(f"⚠️ Peewee falló pero MongoDB tuvo éxito en {operacion} {entidad_id}")
        elif mongo_error:
            logger.warning(f"⚠️ MongoDB falló pero Peewee tuvo éxito en {operacion} {entidad_id}")
        else:
            logger.info(f"✅ {operacion} dual exitoso para {entidad_id}")

    # ──────────────────────────────────────────────────────────────────────────
    # Interfaz pública
    # ──────────────────────────────────────────────────────────────────────────

    def save(self, tarea: Tarea) -> None:
        """
        Guarda la tarea con ping previo a ambas BDD y Circuit Breaker.

        - Si ambas responden: escritura en paralelo.
        - Si solo una responde (o su circuit está OPEN): guarda solo en la disponible.
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
        Obtiene una tarea con Circuit Breaker y Retry.

        Si el Circuit Breaker de SQL está OPEN, salta directo a MongoDB.
        Si SQL está disponible, intenta con retry antes de hacer fallback.

        Args:
            tarea_id: El ID de la tarea.

        Returns:
            La tarea si existe, None en caso contrario.
        """
        logger.debug(f"🔍 Buscando tarea {tarea_id}")

        # ── Intento 1: Peewee (con Circuit Breaker + Retry) ──
        if self._sql_circuit.allow_request():
            try:
                tarea = retry_with_backoff(
                    lambda: self._sql_repo.get(tarea_id),
                    max_retries=_RETRY_MAX_RETRIES,
                    base_delay=_RETRY_BASE_DELAY,
                )
                self._sql_circuit.record_success()
                if tarea is not None:
                    logger.debug(f"✓ Tarea {tarea_id} obtenida de Peewee")
                    return tarea
            except Exception as e:
                self._sql_circuit.record_failure()
                logger.warning(f"⚠️ Error obteniendo de Peewee: {e}")
        else:
            logger.info(
                f"⚡ Peewee circuit OPEN — saltando directo a MongoDB "
                f"para get({tarea_id})"
            )

        # ── Intento 2: MongoDB (fallback, también con Circuit Breaker) ──
        if self._mongo_circuit.allow_request():
            try:
                tarea = retry_with_backoff(
                    lambda: self._mongo_repo.get(tarea_id),
                    max_retries=_RETRY_MAX_RETRIES,
                    base_delay=_RETRY_BASE_DELAY,
                )
                self._mongo_circuit.record_success()
                if tarea is not None:
                    logger.info(f"✓ Tarea {tarea_id} obtenida de MongoDB (fallback)")
                    return tarea
            except Exception as e:
                self._mongo_circuit.record_failure()
                logger.warning(f"⚠️ Error obteniendo de MongoDB: {e}")
        else:
            logger.error(
                f"❌ Ambos Circuit Breakers abiertos — no se puede obtener {tarea_id}"
            )

        logger.debug(f"❌ Tarea {tarea_id} no encontrada en ninguna base de datos")
        return None

    def list(self) -> list[Tarea]:
        """
        Lista todas las tareas con Circuit Breaker y Retry.

        Si el Circuit Breaker de SQL está OPEN, salta directo a MongoDB.

        Returns:
            Lista de todas las tareas.
        """
        logger.debug("📋 Listando todas las tareas")

        # ── Intento 1: Peewee ──
        if self._sql_circuit.allow_request():
            try:
                tareas = retry_with_backoff(
                    lambda: self._sql_repo.list(),
                    max_retries=_RETRY_MAX_RETRIES,
                    base_delay=_RETRY_BASE_DELAY,
                )
                self._sql_circuit.record_success()
                logger.debug(f"✓ Listadas {len(tareas)} tareas de Peewee")
                return tareas
            except Exception as e:
                self._sql_circuit.record_failure()
                logger.warning(f"⚠️ Error listando de Peewee: {e}, intentando MongoDB")
        else:
            logger.info("⚡ Peewee circuit OPEN — saltando directo a MongoDB para list()")

        # ── Intento 2: MongoDB (fallback) ──
        if self._mongo_circuit.allow_request():
            try:
                tareas = retry_with_backoff(
                    lambda: self._mongo_repo.list(),
                    max_retries=_RETRY_MAX_RETRIES,
                    base_delay=_RETRY_BASE_DELAY,
                )
                self._mongo_circuit.record_success()
                logger.info(f"✓ Listadas {len(tareas)} tareas de MongoDB (fallback)")
                return tareas
            except Exception as mongo_error:
                self._mongo_circuit.record_failure()
                logger.error(f"❌ Error listando de MongoDB: {mongo_error}")
                raise Exception(
                    f"Falló el listado en ambas bases de datos. MongoDB: {mongo_error}"
                )
        else:
            raise Exception(
                "Falló el listado: ambos Circuit Breakers en estado OPEN."
            )

    def eliminar(self, tarea_id: UUID) -> None:
        """
        Elimina una tarea con ping previo a ambas BDD y Circuit Breaker.

        - Si ambas responden: eliminación en paralelo.
        - Si solo una responde (o su circuit está OPEN): elimina solo en la disponible.
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
