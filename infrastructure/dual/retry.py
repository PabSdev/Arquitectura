"""
Retry con Exponential Backoff para operaciones de infraestructura.

Inspirado en el skill python-testing-patterns (Pattern: Testing Retry Behavior).
Solo reintenta errores TRANSITORIOS de red/conexión, no errores de lógica.
"""

import time
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

# ── Excepciones transitorias que justifican un retry ──────────────────────────
# Se importan de forma segura para no crear dependencias duras.
_RETRYABLE_EXCEPTIONS: list[type] = [ConnectionError, TimeoutError, OSError]

try:
    from sqlalchemy.exc import OperationalError, DisconnectionError

    _RETRYABLE_EXCEPTIONS.extend([OperationalError, DisconnectionError])
except ImportError:
    pass

try:
    from pymongo.errors import (
        ConnectionFailure,
        ServerSelectionTimeoutError,
        AutoReconnect,
    )

    _RETRYABLE_EXCEPTIONS.extend(
        [ConnectionFailure, ServerSelectionTimeoutError, AutoReconnect]
    )
except ImportError:
    pass

RETRYABLE_EXCEPTIONS = tuple(_RETRYABLE_EXCEPTIONS)


def retry_with_backoff(
    func: Callable[[], Any],
    max_retries: int = 2,
    base_delay: float = 0.5,
    retryable_exceptions: tuple[type, ...] = RETRYABLE_EXCEPTIONS,
) -> Any:
    """
    Ejecuta `func()` con reintentos y backoff exponencial.

    Solo reintenta las excepciones indicadas en `retryable_exceptions`.
    Cualquier otra excepción se propaga inmediatamente sin reintentar.

    Args:
        func:                  Callable sin argumentos a ejecutar.
        max_retries:           Número máximo de reintentos (sin contar el intento original).
        base_delay:            Delay base en segundos (se duplica en cada retry).
        retryable_exceptions:  Tupla de excepciones que justifican un retry.

    Returns:
        El resultado de `func()`.

    Raises:
        La última excepción si se agotan los reintentos,
        o la excepción original si no es retryable.
    """
    last_exception: Exception | None = None

    for attempt in range(1, max_retries + 2):  # +2 porque incluye intento original
        try:
            return func()
        except retryable_exceptions as e:
            last_exception = e
            if attempt <= max_retries:
                delay = base_delay * (2 ** (attempt - 1))
                logger.warning(
                    f"🔁 Retry {attempt}/{max_retries} tras error transitorio: {e}. "
                    f"Esperando {delay:.1f}s..."
                )
                time.sleep(delay)
            else:
                logger.error(
                    f"❌ Agotados {max_retries} reintentos. Último error: {e}"
                )
        # Excepciones NO retryable → se propagan inmediatamente
        # (no hay except genérico aquí, así que se elevan solas)

    raise last_exception  # type: ignore[misc]
