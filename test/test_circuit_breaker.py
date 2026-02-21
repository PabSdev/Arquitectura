"""
Tests para CircuitBreaker y retry_with_backoff.

Aplica patrones del skill python-testing-patterns:
- Pattern 3: Parametrized Tests
- Pattern 4: Mocking con side_effect
- Pattern: Testing Retry Behavior
"""

import time
import pytest
from unittest.mock import Mock, patch

from infrastructure.dual.circuit_breaker import CircuitBreaker
from infrastructure.dual.retry import retry_with_backoff, RETRYABLE_EXCEPTIONS


# ══════════════════════════════════════════════════════════════════════════════
# Circuit Breaker Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestCircuitBreaker:
    """Suite de tests para el Circuit Breaker."""

    @pytest.fixture
    def cb(self):
        """Circuit Breaker con threshold bajo para tests rápidos."""
        return CircuitBreaker(
            name="TestDB",
            failure_threshold=3,
            recovery_timeout=1.0,  # 1 segundo para tests rápidos
        )

    # ── Estado inicial ────────────────────────────────────────────────────────

    def test_initial_state_is_closed(self, cb):
        """El circuito empieza en CLOSED."""
        assert cb.state == CircuitBreaker.CLOSED
        assert cb.allow_request() is True

    # ── Transición CLOSED → OPEN ──────────────────────────────────────────────

    def test_opens_after_reaching_failure_threshold(self, cb):
        """Tras N fallos consecutivos, el circuito se abre."""
        for _ in range(3):
            cb.record_failure()

        assert cb.state == CircuitBreaker.OPEN
        assert cb.allow_request() is False

    def test_stays_closed_below_threshold(self, cb):
        """No se abre si los fallos están por debajo del threshold."""
        cb.record_failure()
        cb.record_failure()  # 2 < 3

        assert cb.state == CircuitBreaker.CLOSED
        assert cb.allow_request() is True

    def test_success_resets_failure_count(self, cb):
        """Un éxito resetea el contador de fallos."""
        cb.record_failure()
        cb.record_failure()
        cb.record_success()  # Reset
        cb.record_failure()  # Solo 1 fallo ahora

        assert cb.state == CircuitBreaker.CLOSED

    # ── Transición OPEN → HALF_OPEN ──────────────────────────────────────────

    def test_transitions_to_half_open_after_recovery_timeout(self, cb):
        """Tras el recovery_timeout, el circuito pasa a HALF_OPEN."""
        # Abrir el circuito
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitBreaker.OPEN

        # Esperar recovery_timeout
        time.sleep(1.1)  # > 1.0s recovery_timeout

        assert cb.state == CircuitBreaker.HALF_OPEN
        assert cb.allow_request() is True  # Permite 1 request de prueba

    # ── Transición HALF_OPEN → CLOSED ────────────────────────────────────────

    def test_closes_on_success_in_half_open(self, cb):
        """En HALF_OPEN, un éxito cierra el circuito."""
        for _ in range(3):
            cb.record_failure()

        time.sleep(1.1)
        assert cb.state == CircuitBreaker.HALF_OPEN

        cb.record_success()
        assert cb.state == CircuitBreaker.CLOSED
        assert cb.allow_request() is True

    # ── Transición HALF_OPEN → OPEN ──────────────────────────────────────────

    def test_reopens_on_failure_in_half_open(self, cb):
        """En HALF_OPEN, un fallo vuelve a OPEN."""
        for _ in range(3):
            cb.record_failure()

        time.sleep(1.1)
        assert cb.state == CircuitBreaker.HALF_OPEN

        cb.record_failure()
        assert cb.state == CircuitBreaker.OPEN
        assert cb.allow_request() is False

    # ── Reset ─────────────────────────────────────────────────────────────────

    def test_reset_returns_to_initial_state(self, cb):
        """reset() devuelve todo al estado inicial."""
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitBreaker.OPEN

        cb.reset()
        assert cb.state == CircuitBreaker.CLOSED
        assert cb.allow_request() is True


# ══════════════════════════════════════════════════════════════════════════════
# Retry Tests
# ══════════════════════════════════════════════════════════════════════════════


class TestRetryWithBackoff:
    """Suite de tests para retry_with_backoff."""

    def test_succeeds_on_first_attempt(self):
        """Si la función funciona, retorna directamente sin retry."""
        func = Mock(return_value="ok")

        result = retry_with_backoff(func, max_retries=2)

        assert result == "ok"
        assert func.call_count == 1

    def test_succeeds_on_second_attempt(self):
        """Retry recupera de un error transitorio en el segundo intento."""
        func = Mock(side_effect=[ConnectionError("timeout"), "ok"])

        result = retry_with_backoff(func, max_retries=2, base_delay=0.01)

        assert result == "ok"
        assert func.call_count == 2

    def test_succeeds_on_last_attempt(self):
        """Retry tiene éxito en el último intento permitido."""
        func = Mock(side_effect=[
            ConnectionError("fail 1"),
            ConnectionError("fail 2"),
            "ok",
        ])

        result = retry_with_backoff(func, max_retries=2, base_delay=0.01)

        assert result == "ok"
        assert func.call_count == 3

    def test_gives_up_after_max_retries(self):
        """Se rinde y lanza la última excepción tras max_retries."""
        func = Mock(side_effect=ConnectionError("persistent failure"))

        with pytest.raises(ConnectionError, match="persistent failure"):
            retry_with_backoff(func, max_retries=2, base_delay=0.01)

        assert func.call_count == 3  # 1 original + 2 retries

    def test_does_not_retry_non_retryable_exception(self):
        """No reintenta excepciones que no son transitorias."""
        func = Mock(side_effect=ValueError("bad input"))

        with pytest.raises(ValueError, match="bad input"):
            retry_with_backoff(func, max_retries=2, base_delay=0.01)

        assert func.call_count == 1  # Solo 1 intento

    def test_does_not_retry_key_error(self):
        """KeyError no es retryable — falla inmediatamente."""
        func = Mock(side_effect=KeyError("missing"))

        with pytest.raises(KeyError):
            retry_with_backoff(func, max_retries=3, base_delay=0.01)

        assert func.call_count == 1

    @pytest.mark.parametrize("exception_class", [
        ConnectionError,
        TimeoutError,
        OSError,
    ])
    def test_retries_all_retryable_exception_types(self, exception_class):
        """Verifica que todas las excepciones retryable se reintentan."""
        func = Mock(side_effect=[exception_class("error"), "ok"])

        result = retry_with_backoff(func, max_retries=2, base_delay=0.01)

        assert result == "ok"
        assert func.call_count == 2
