from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from core.domain.models.tarea import EstadoTarea, Tarea
from infrastructure.mongo.repository.tarea_repository import MongoTareaRepository


@pytest.fixture
def mock_mongo_collection():
    collection = MagicMock()
    return collection


@pytest.fixture
def mongo_repository(mock_mongo_collection):
    repo = MongoTareaRepository()
    repo.collection = mock_mongo_collection
    return repo


def test_save_tarea(mongo_repository, mock_mongo_collection):
    tarea = Tarea(
        id=uuid4(),
        titulo="Test Tarea",
        descripcion="Test Descripcion",
        estado=EstadoTarea.PENDIENTE,
    )

    mongo_repository.save(tarea)

    mock_mongo_collection.update_one.assert_called_once()
    args, kwargs = mock_mongo_collection.update_one.call_args
    assert args[0] == {"_id": str(tarea.id)}
    assert kwargs["upsert"] is True


def test_get_tarea_found(mongo_repository, mock_mongo_collection):
    tarea_id = uuid4()
    mock_doc = {
        "_id": str(tarea_id),
        "titulo": "Found Tarea",
        "descripcion": "Found Descripcion",
        "estado": "pendiente",
    }
    mock_mongo_collection.find_one.return_value = mock_doc

    result = mongo_repository.get(tarea_id)

    assert result is not None
    assert result.id == tarea_id
    assert result.titulo == "Found Tarea"


def test_get_tarea_not_found(mongo_repository, mock_mongo_collection):
    mock_mongo_collection.find_one.return_value = None

    result = mongo_repository.get(uuid4())

    assert result is None


def test_list_tareas(mongo_repository, mock_mongo_collection):
    mock_docs = [
        {
            "_id": str(uuid4()),
            "titulo": "Tarea 1",
            "descripcion": "Desc 1",
            "estado": "pendiente",
        },
        {
            "_id": str(uuid4()),
            "titulo": "Tarea 2",
            "descripcion": "Desc 2",
            "estado": "completada",
        },
    ]
    mock_mongo_collection.find.return_value = mock_docs

    results = mongo_repository.list()

    assert len(results) == 2
    assert results[0].titulo == "Tarea 1"
    assert results[1].titulo == "Tarea 2"


def test_eliminar_tarea(mongo_repository, mock_mongo_collection):
    tarea_id = uuid4()
    mongo_repository.eliminar(tarea_id)

    mock_mongo_collection.delete_one.assert_called_once_with({"_id": str(tarea_id)})
