"""
Circuit Breaker para proteger operaciones de base de datos.

Patrón inspirado en el skill async-python-patterns (Pattern 5: Timeout Handling).
Evita golpear repetidamente una BDD que sabemos que está caída.

Estados:
    CLOSED    → Funciona normal. Cuenta fallos consecutivos.
    OPEN      → BDD considerada caída. Llamadas se saltan directo (→ fallback).
    HALF_OPEN → Deja pasar 1 request de prueba para verificar recuperación.
"""

import time
import logging
import threading

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """
    Circuit Breaker thread-safe para operaciones de infraestructura.

    Args:
        name:              Nombre descriptivo (para logs), ej: "SQLAlchemy", "MongoDB".
        failure_threshold: Número de fallos consecutivos para abrir el circuito.
        recovery_timeout:  Segundos que permanece OPEN antes de pasar a HALF_OPEN.
    """

    # Estados posibles
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

    def __init__(
        self,
        name: str = "default",
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self._state = self.CLOSED
        self._failure_count = 0
        self._last_failure_time: float | None = None
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        """Estado actual del circuito, evaluado dinámicamente."""
        with self._lock:
            if self._state == self.OPEN and self._last_failure_time is not None:
                elapsed = time.monotonic() - self._last_failure_time
                if elapsed >= self.recovery_timeout:
                    self._state = self.HALF_OPEN
                    logger.info(
                        f"🔄 Circuit Breaker [{self.name}]: OPEN → HALF_OPEN "
                        f"(tras {elapsed:.1f}s)"
                    )
            return self._state

    def allow_request(self) -> bool:
        """
        ¿Se permite enviar un request a esta BDD?

        Returns:
            True si el circuito permite la operación.
        """
        current_state = self.state  # Evalúa posible transición OPEN → HALF_OPEN
        if current_state == self.CLOSED:
            return True
        if current_state == self.HALF_OPEN:
            return True  # Permite 1 request de prueba
        # OPEN → no permitir
        return False

    def record_success(self) -> None:
        """Registra una operación exitosa. Cierra el circuito si estaba HALF_OPEN."""
        with self._lock:
            if self._state == self.HALF_OPEN:
                logger.info(
                    f"✅ Circuit Breaker [{self.name}]: HALF_OPEN → CLOSED "
                    f"(operación de prueba exitosa)"
                )
            self._state = self.CLOSED
            self._failure_count = 0
            self._last_failure_time = None

    def record_failure(self) -> None:
        """
        Registra un fallo. Abre el circuito si se alcanza el threshold.
        """
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self._state == self.HALF_OPEN:
                # La prueba falló → volver a OPEN
                self._state = self.OPEN
                logger.warning(
                    f"🔴 Circuit Breaker [{self.name}]: HALF_OPEN → OPEN "
                    f"(prueba falló)"
                )
            elif self._failure_count >= self.failure_threshold:
                self._state = self.OPEN
                logger.warning(
                    f"🔴 Circuit Breaker [{self.name}]: CLOSED → OPEN "
                    f"(fallos consecutivos: {self._failure_count})"
                )

    def reset(self) -> None:
        """Reinicia el Circuit Breaker al estado inicial (para testing)."""
        with self._lock:
            self._state = self.CLOSED
            self._failure_count = 0
            self._last_failure_time = None
