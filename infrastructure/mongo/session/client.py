import os
from typing import Any

from pymongo import MongoClient
from pymongo.database import Database

_client: MongoClient[Any] | None = None


def get_client() -> MongoClient[Any]:
    """
    Obtiene el cliente de MongoDB (Singleton).
    """
    global _client
    if _client is None:
        mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        _client = MongoClient(mongo_uri)
    return _client


def get_db() -> Database[Any]:
    """
    Obtiene la base de datos de MongoDB.

    Retorna:
        Database: La instancia de la base de datos de MongoDB.
    """
    client = get_client()
    db_name = os.getenv("MONGO_DB_NAME", "mi_proyecto")
    return client[db_name]
