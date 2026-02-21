"""
Tests para el DualTareaRepository.
Verifica operaciones duales, Circuit Breaker, Retry y fallback.
"""

import pytest
from uuid import uuid4
from unittest.mock import Mock, patch, call
from concurrent.futures import ThreadPoolExecutor

from core.domain.models.tarea import Tarea, EstadoTarea
from infrastructure.dual.repository.tarea_repository import DualTareaRepository


class TestDualTareaRepository:
    """Suite de tests para el repositorio dual."""

    @pytest.fixture
    def mock_sql_repo(self):
        """Mock del repositorio SQLAlchemy."""
        return Mock()

    @pytest.fixture
    def mock_mongo_repo(self):
        """Mock del repositorio MongoDB."""
        return Mock()

    @pytest.fixture
    def dual_repo(self, mock_sql_repo, mock_mongo_repo):
        """Fixture del repositorio dual con mocks."""
        return DualTareaRepository(
            sql_repository=mock_sql_repo, mongo_repository=mock_mongo_repo
        )

    @pytest.fixture
    def tarea_ejemplo(self):
        """Fixture de una tarea de ejemplo."""
        return Tarea(
            id=uuid4(),
            titulo="Tarea de prueba",
            descripcion="Descripción de prueba",
            estado=EstadoTarea.PENDIENTE,
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Tests de operaciones básicas (save, get, list, eliminar)
    # ──────────────────────────────────────────────────────────────────────────

    def test_save_ejecuta_en_ambos_repositorios(
        self, dual_repo, mock_sql_repo, mock_mongo_repo, tarea_ejemplo
    ):
        """Test: save() debe llamar a ambos repositorios."""
        # Act
        dual_repo.save(tarea_ejemplo)

        # Assert
        mock_sql_repo.save.assert_called_once_with(tarea_ejemplo)
        mock_mongo_repo.save.assert_called_once_with(tarea_ejemplo)

    def test_save_falla_si_ambos_repositorios_fallan(
        self, dual_repo, mock_sql_repo, mock_mongo_repo, tarea_ejemplo
    ):
        """Test: save() debe lanzar excepción si ambas DBs fallan."""
        # Arrange
        mock_sql_repo.save.side_effect = Exception("Error SQL")
        mock_mongo_repo.save.side_effect = Exception("Error Mongo")

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            dual_repo.save(tarea_ejemplo)

        assert "ambas bases de datos" in str(exc_info.value).lower()

    def test_save_continua_si_solo_sql_falla(
        self, dual_repo, mock_sql_repo, mock_mongo_repo, tarea_ejemplo
    ):
        """Test: save() debe continuar si solo SQLAlchemy falla."""
        # Arrange
        mock_sql_repo.save.side_effect = Exception("Error SQL")
        mock_mongo_repo.save.return_value = None  # Éxito en Mongo

        # Act - No debe lanzar excepción
        dual_repo.save(tarea_ejemplo)

        # Assert
        mock_mongo_repo.save.assert_called_once_with(tarea_ejemplo)

    def test_save_continua_si_solo_mongo_falla(
        self, dual_repo, mock_sql_repo, mock_mongo_repo, tarea_ejemplo
    ):
        """Test: save() debe continuar si solo MongoDB falla."""
        # Arrange
        mock_sql_repo.save.return_value = None  # Éxito en SQL
        mock_mongo_repo.save.side_effect = Exception("Error Mongo")

        # Act - No debe lanzar excepción
        dual_repo.save(tarea_ejemplo)

        # Assert
        mock_sql_repo.save.assert_called_once_with(tarea_ejemplo)

    def test_get_intenta_sql_primero(
        self, dual_repo, mock_sql_repo, mock_mongo_repo, tarea_ejemplo
    ):
        """Test: get() debe intentar SQLAlchemy primero."""
        # Arrange
        mock_sql_repo.get.return_value = tarea_ejemplo
        tarea_id = tarea_ejemplo.id

        # Act
        resultado = dual_repo.get(tarea_id)

        # Assert
        assert resultado == tarea_ejemplo
        mock_sql_repo.get.assert_called_once_with(tarea_id)
        mock_mongo_repo.get.assert_not_called()  # No debe llamar a Mongo

    def test_get_usa_fallback_a_mongo(
        self, dual_repo, mock_sql_repo, mock_mongo_repo, tarea_ejemplo
    ):
        """Test: get() debe usar MongoDB como fallback si SQL falla."""
        # Arrange
        mock_sql_repo.get.return_value = None  # No encontrado en SQL
        mock_mongo_repo.get.return_value = tarea_ejemplo
        tarea_id = tarea_ejemplo.id

        # Act
        resultado = dual_repo.get(tarea_id)

        # Assert
        assert resultado == tarea_ejemplo
        mock_sql_repo.get.assert_called_once_with(tarea_id)
        mock_mongo_repo.get.assert_called_once_with(tarea_id)

    def test_get_retorna_none_si_no_existe_en_ninguna_db(
        self, dual_repo, mock_sql_repo, mock_mongo_repo
    ):
        """Test: get() debe retornar None si no existe en ninguna DB."""
        # Arrange
        tarea_id = uuid4()
        mock_sql_repo.get.return_value = None
        mock_mongo_repo.get.return_value = None

        # Act
        resultado = dual_repo.get(tarea_id)

        # Assert
        assert resultado is None

    def test_list_usa_sql_por_defecto(
        self, dual_repo, mock_sql_repo, mock_mongo_repo, tarea_ejemplo
    ):
        """Test: list() debe usar SQLAlchemy por defecto."""
        # Arrange
        tareas = [tarea_ejemplo]
        mock_sql_repo.list.return_value = tareas

        # Act
        resultado = dual_repo.list()

        # Assert
        assert resultado == tareas
        mock_sql_repo.list.assert_called_once()
        mock_mongo_repo.list.assert_not_called()

    def test_list_usa_fallback_a_mongo(
        self, dual_repo, mock_sql_repo, mock_mongo_repo, tarea_ejemplo
    ):
        """Test: list() debe usar MongoDB como fallback si SQL falla."""
        # Arrange
        tareas = [tarea_ejemplo]
        mock_sql_repo.list.side_effect = Exception("Error SQL")
        mock_mongo_repo.list.return_value = tareas

        # Act
        resultado = dual_repo.list()

        # Assert
        assert resultado == tareas
        mock_mongo_repo.list.assert_called_once()

    def test_eliminar_ejecuta_en_ambos_repositorios(
        self, dual_repo, mock_sql_repo, mock_mongo_repo
    ):
        """Test: eliminar() debe llamar a ambos repositorios."""
        # Arrange
        tarea_id = uuid4()

        # Act
        dual_repo.eliminar(tarea_id)

        # Assert
        mock_sql_repo.eliminar.assert_called_once_with(tarea_id)
        mock_mongo_repo.eliminar.assert_called_once_with(tarea_id)

    def test_eliminar_falla_si_ambos_repositorios_fallan(
        self, dual_repo, mock_sql_repo, mock_mongo_repo
    ):
        """Test: eliminar() debe lanzar excepción si ambas DBs fallan."""
        # Arrange
        tarea_id = uuid4()
        mock_sql_repo.eliminar.side_effect = Exception("Error SQL")
        mock_mongo_repo.eliminar.side_effect = Exception("Error Mongo")

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            dual_repo.eliminar(tarea_id)

        assert "ambas bases de datos" in str(exc_info.value).lower()

    def test_eliminar_continua_si_solo_una_falla(
        self, dual_repo, mock_sql_repo, mock_mongo_repo
    ):
        """Test: eliminar() debe continuar si solo una DB falla."""
        # Arrange
        tarea_id = uuid4()
        mock_sql_repo.eliminar.side_effect = Exception("Error SQL")
        mock_mongo_repo.eliminar.return_value = None  # Éxito en Mongo

        # Act - No debe lanzar excepción
        dual_repo.eliminar(tarea_id)

        # Assert
        mock_mongo_repo.eliminar.assert_called_once_with(tarea_id)

    def test_execute_parallel_ejecuta_ambas_funciones(
        self, dual_repo
    ):
        """Test: _execute_parallel() debe ejecutar ambas funciones."""
        # Arrange
        func1 = Mock(return_value="resultado1")
        func2 = Mock(return_value="resultado2")

        # Act
        sql_result, sql_error, mongo_result, mongo_error = (
            dual_repo._execute_parallel(func1, func2)
        )

        # Assert
        func1.assert_called_once()
        func2.assert_called_once()
        assert sql_result == "resultado1"
        assert mongo_result == "resultado2"
        assert sql_error is None
        assert mongo_error is None

    def test_execute_parallel_captura_errores(self, dual_repo):
        """Test: _execute_parallel() debe capturar errores de ambas funciones."""
        # Arrange
        func1 = Mock(side_effect=Exception("Error 1"))
        func2 = Mock(side_effect=Exception("Error 2"))

        # Act
        sql_result, sql_error, mongo_result, mongo_error = (
            dual_repo._execute_parallel(func1, func2)
        )

        # Assert
        assert sql_result is None
        assert mongo_result is None
        assert sql_error is not None
        assert mongo_error is not None
        assert "Error 1" in str(sql_error)
        assert "Error 2" in str(mongo_error)

    # ──────────────────────────────────────────────────────────────────────────
    # Tests de Circuit Breaker integrado en DualTareaRepository
    # ──────────────────────────────────────────────────────────────────────────

    def test_get_skips_sql_when_circuit_open(
        self, dual_repo, mock_sql_repo, mock_mongo_repo, tarea_ejemplo
    ):
        """get() va directo a Mongo si el Circuit Breaker de SQL está OPEN."""
        # Arrange — Forzar apertura del circuito SQL
        for _ in range(3):
            dual_repo._sql_circuit.record_failure()
        assert dual_repo._sql_circuit.state == "OPEN"

        mock_mongo_repo.get.return_value = tarea_ejemplo

        # Act
        resultado = dual_repo.get(tarea_ejemplo.id)

        # Assert
        assert resultado == tarea_ejemplo
        mock_sql_repo.get.assert_not_called()  # SQL fue saltado
        mock_mongo_repo.get.assert_called_once_with(tarea_ejemplo.id)

    def test_list_skips_sql_when_circuit_open(
        self, dual_repo, mock_sql_repo, mock_mongo_repo, tarea_ejemplo
    ):
        """list() va directo a Mongo si el Circuit Breaker de SQL está OPEN."""
        # Arrange — Forzar apertura del circuito SQL
        for _ in range(3):
            dual_repo._sql_circuit.record_failure()

        tareas = [tarea_ejemplo]
        mock_mongo_repo.list.return_value = tareas

        # Act
        resultado = dual_repo.list()

        # Assert
        assert resultado == tareas
        mock_sql_repo.list.assert_not_called()
        mock_mongo_repo.list.assert_called_once()

    def test_circuit_breaker_records_success_on_sql_read(
        self, dual_repo, mock_sql_repo, mock_mongo_repo, tarea_ejemplo
    ):
        """Un get() exitoso de SQL registra éxito en el Circuit Breaker."""
        # Arrange
        mock_sql_repo.get.return_value = tarea_ejemplo

        # Act
        dual_repo.get(tarea_ejemplo.id)

        # Assert
        assert dual_repo._sql_circuit.state == "CLOSED"
        assert dual_repo._sql_circuit._failure_count == 0

    def test_circuit_breaker_records_failure_on_sql_exception(
        self, dual_repo, mock_sql_repo, mock_mongo_repo
    ):
        """Si SQL lanza excepción en get(), se registra fallo en Circuit Breaker."""
        # Arrange
        mock_sql_repo.get.side_effect = Exception("SQL error")
        mock_mongo_repo.get.return_value = None

        # Act
        dual_repo.get(uuid4())

        # Assert — el fallo se contabiliza
        assert dual_repo._sql_circuit._failure_count > 0

    def test_get_fallback_when_sql_errors_accumulate(
        self, dual_repo, mock_sql_repo, mock_mongo_repo, tarea_ejemplo
    ):
        """Tras 3 fallos consecutivos de SQL, get() salta directo a Mongo."""
        # Arrange — Simular 3 fallos consecutivos en get()
        mock_sql_repo.get.side_effect = ConnectionError("SQL down")
        mock_mongo_repo.get.return_value = tarea_ejemplo

        # Act — 3 llamadas para abrir el circuito
        for _ in range(3):
            dual_repo.get(tarea_ejemplo.id)

        # Reset mocks para la 4ta llamada
        mock_sql_repo.get.reset_mock()
        mock_mongo_repo.get.reset_mock()
        mock_mongo_repo.get.return_value = tarea_ejemplo

        # Act — 4ta llamada: circuit debería estar OPEN
        resultado = dual_repo.get(tarea_ejemplo.id)

        # Assert
        assert resultado == tarea_ejemplo
        mock_sql_repo.get.assert_not_called()  # SQL fue saltado
        mock_mongo_repo.get.assert_called_once()

    def test_list_raises_when_both_circuits_open(
        self, dual_repo, mock_sql_repo, mock_mongo_repo
    ):
        """list() lanza excepción si ambos Circuit Breakers están abiertos."""
        # Arrange — Abrir ambos circuitos
        for _ in range(3):
            dual_repo._sql_circuit.record_failure()
            dual_repo._mongo_circuit.record_failure()

        # Act & Assert
        with pytest.raises(Exception, match="Circuit Breakers"):
            dual_repo.list()

    # ──────────────────────────────────────────────────────────────────────────
    # Tests de Retry integrado
    # ──────────────────────────────────────────────────────────────────────────

    def test_get_recovers_from_transient_sql_error(
        self, dual_repo, mock_sql_repo, mock_mongo_repo, tarea_ejemplo
    ):
        """get() reintenta y recupera de un error transitorio de SQL."""
        # Arrange — Falla 1 vez, luego éxito
        mock_sql_repo.get.side_effect = [
            ConnectionError("transient"),
            tarea_ejemplo,
        ]

        # Act
        resultado = dual_repo.get(tarea_ejemplo.id)

        # Assert
        assert resultado == tarea_ejemplo
        assert mock_sql_repo.get.call_count == 2
        mock_mongo_repo.get.assert_not_called()

    def test_list_recovers_from_transient_sql_error(
        self, dual_repo, mock_sql_repo, mock_mongo_repo, tarea_ejemplo
    ):
        """list() reintenta y recupera de un error transitorio de SQL."""
        # Arrange
        tareas = [tarea_ejemplo]
        mock_sql_repo.list.side_effect = [
            ConnectionError("transient"),
            tareas,
        ]

        # Act
        resultado = dual_repo.list()

        # Assert
        assert resultado == tareas
        assert mock_sql_repo.list.call_count == 2
        mock_mongo_repo.list.assert_not_called()


class TestDualTareaRepositoryIntegration:
    """Tests de integración (requieren bases de datos reales)."""

    @pytest.mark.integration
    def test_dual_write_integration(self):
        """Test de integración: Verifica escritura dual real."""
        # Este test requiere ambas DBs configuradas
        from infrastructure.sqlalchemy.repository.tarea_repository import (
            SqlAlchemyTareaRepository,
        )
        from infrastructure.mongo.repository.tarea_repository import (
            MongoTareaRepository,
        )

        # Arrange
        sql_repo = SqlAlchemyTareaRepository()
        mongo_repo = MongoTareaRepository()
        dual_repo = DualTareaRepository(
            sql_repository=sql_repo, mongo_repository=mongo_repo
        )

        tarea = Tarea(
            id=uuid4(),
            titulo="Test Integración Dual",
            descripcion="Prueba de escritura dual real",
            estado=EstadoTarea.PENDIENTE,
        )

        # Act
        dual_repo.save(tarea)

        # Assert - Verificar que existe en ambas DBs
        tarea_sql = sql_repo.get(tarea.id)
        tarea_mongo = mongo_repo.get(tarea.id)

        assert tarea_sql is not None
        assert tarea_mongo is not None
        assert tarea_sql.titulo == tarea.titulo
        assert tarea_mongo.titulo == tarea.titulo

        # Cleanup
        dual_repo.eliminar(tarea.id)
