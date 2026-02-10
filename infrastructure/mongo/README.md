# MongoDB Infrastructure

## 📖 Descripción

Implementación del repositorio de tareas usando **MongoDB** como base de datos NoSQL documental. Este módulo proporciona la capa de persistencia orientada a documentos siguiendo los principios de la arquitectura hexagonal.

## 🎯 Objetivo

Proporcionar una implementación flexible y escalable del puerto `TareaRepository` usando MongoDB, aprovechando las ventajas de las bases de datos documentales (esquema flexible, alta disponibilidad, escalabilidad horizontal).

---

## 🏗️ Arquitectura

### Diagrama de Componentes

```mermaid
graph TB
    subgraph "Application Layer"
        UC[Use Cases]
    end
    
    subgraph "Domain Layer"
        Port[TareaRepository Port]
        Domain[Tarea Domain Model]
    end
    
    subgraph "Infrastructure Layer - MongoDB"
        Repo[MongoTareaRepository]
        Model[TareaMongo Pydantic Model]
        Client[MongoClient Singleton]
        DB[(MongoDB Database)]
        
        Repo -->|usa| Client
        Client -->|conecta| DB
        Repo -->|serializa/deserializa| Model
        Model -->|persiste| DB
    end
    
    UC -->|inyecta| Port
    Port -.->|implementa| Repo
    Repo -->|retorna| Domain
```

### Diagrama de Flujo de Datos

```mermaid
sequenceDiagram
    participant UseCase as Use Case
    participant Repo as MongoTareaRepository
    participant Model as TareaMongo
    participant Client as MongoClient
    participant DB as MongoDB
    
    UseCase->>Repo: save(tarea)
    Repo->>Model: from_domain(tarea)
    Model-->>Repo: tarea_mongo
    
    Repo->>Model: model_dump(by_alias=True)
    Model-->>Repo: tarea_dict
    
    Repo->>Client: collection.update_one()
    Client->>DB: db.tareas.updateOne()
    DB-->>Client: acknowledged
    Client-->>Repo: UpdateResult
    Repo-->>UseCase: return
    
    Note over Repo,Client: upsert=true: inserta o actualiza
```

### Mapeo Documento <-> Dominio

```mermaid
graph LR
    subgraph "Domain Model"
        D1[id: UUID]
        D2[titulo: str]
        D3[descripcion: str]
        D4[estado: EstadoTarea]
    end
    
    subgraph "SQLAlchemy Model"
        M1[id: String]
        M2[titulo: String]
        M3[descripcion: Text]
        M4[estado: String]
    end
    
    D1 -->|"str()"| M1
    M1 -->|"UUID()"| D1
    D4 -->|"value"| M4
    M4 -->|"EstadoTarea()"| D4
```

---

## 📁 Estructura de Archivos

```
infrastructure/mongo/
├── session/
│   └── client.py           # Cliente MongoDB (Singleton)
├── models/
│   └── tarea.py            # Modelo Pydantic para MongoDB
└── repository/
    └── tarea_repository.py # Implementación del repositorio
```

---

## 🔧 Configuración

### Variables de Entorno

```bash
# URI de conexión a MongoDB
MONGO_URI=mongodb://localhost:27017
# Para MongoDB Atlas:
# MONGO_URI=mongodb+srv://user:password@cluster.mongodb.net

# Nombre de la base de datos
MONGO_DB_NAME=mi_proyecto
```

### Configuración del Cliente

```python
# infrastructure/mongo/session/client.py
_client: MongoClient[Any] | None = None

def get_client() -> MongoClient[Any]:
    """Obtiene el cliente de MongoDB (Singleton)."""
    global _client
    if _client is None:
        mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        _client = MongoClient(mongo_uri)
    return _client
```

---

## 🚀 Uso

### Usar el Repositorio Directamente

```python
from uuid import uuid4
from infrastructure.mongo.repository.tarea_repository import MongoTareaRepository
from core.domain.models.tarea import Tarea, EstadoTarea

# Crear instancia del repositorio
repo = MongoTareaRepository()

# Crear una tarea
tarea = Tarea(
    id=uuid4(),
    titulo="Mi tarea",
    descripcion="Descripción de la tarea",
    estado=EstadoTarea.PENDIENTE
)

# Guardar
repo.save(tarea)

# Obtener
tarea_obtenida = repo.get(tarea.id)

# Listar todas
tareas = repo.list()

# Eliminar
repo.eliminar(tarea.id)
```

### Uso desde el Container

```python
import os
os.environ["ORM"] = "mongo"

from infrastructure.container import get_crear_tarea_use_case
from core.application.crear_tarea import CrearTareaCommand

use_case = get_crear_tarea_use_case()
cmd = CrearTareaCommand(
    titulo="Nueva tarea",
    descripcion="Descripción",
    estado="pendiente"
)
tarea = use_case.execute(cmd)
```

---

## 🧪 Testing

### Ejecutar Tests

```bash
# Tests específicos de MongoDB
pytest test/test_mongo_repository.py -v

# Todos los tests
pytest test/ -v
```

### MongoDB en Memoria (Para Tests)

Para tests unitarios, puedes usar **mongomock**:

```python
import mongomock
import os
from unittest.mock import patch

@pytest.fixture
def mock_repo():
    os.environ["MONGO_URI"] = "mongodb://localhost:27017"
    client = mongomock.MongoClient()
    
    def mock_get_db():
        return client.test_db
    
    with patch('infrastructure.mongo.repository.tarea_repository.get_db', mock_get_db):
        repo = MongoTareaRepository()
        yield repo
```

---

## 📝 Modelo de Datos

### TareaMongo (Modelo Pydantic)

```python
class TareaMongo(BaseModel):
    """
    Modelo de Tarea para MongoDB.
    Representa como se almacena la tarea en la base de datos.
    """
    
    id: str = Field(alias="_id")
    titulo: str
    descripcion: str | None = None
    estado: str
    
    model_config = {"populate_by_name": True}
    
    def to_domain(self) -> Tarea:
        """Convierte el modelo de MongoDB al modelo de dominio."""
        return Tarea(
            id=UUID(self.id),
            titulo=self.titulo,
            descripcion=self.descripcion,
            estado=EstadoTarea(self.estado),
        )
    
    @classmethod
    def from_domain(cls, tarea: Tarea) -> "TareaMongo":
        """Crea una instancia de TareaMongo a partir de una entidad de dominio."""
        return cls(
            id=str(tarea.id),
            titulo=tarea.titulo,
            descripcion=tarea.descripcion,
            estado=tarea.estado.value,
        )
```

### Estructura del Documento en MongoDB

```json
{
  "_id": "550e8400-e29b-41d4-a716-446655440000",
  "titulo": "Mi tarea",
  "descripcion": "Descripción de ejemplo",
  "estado": "pendiente"
}
```

---

## 🛠️ Guía para Desarrolladores

### Agregar un Nuevo Campo a Tarea

**1. Actualizar el Modelo Pydantic:**

```python
# infrastructure/mongo/models/tarea.py
from datetime import datetime

class TareaMongo(BaseModel):
    id: str = Field(alias="_id")
    titulo: str
    descripcion: str | None = None
    estado: str
    fecha_creacion: datetime | None = None  # NUEVO
    
    model_config = {"populate_by_name": True}
    
    def to_domain(self) -> Tarea:
        return Tarea(
            id=UUID(self.id),
            titulo=self.titulo,
            descripcion=self.descripcion,
            estado=EstadoTarea(self.estado),
            fecha_creacion=self.fecha_creacion,  # NUEVO
        )
    
    @classmethod
    def from_domain(cls, tarea: Tarea) -> "TareaMongo":
        return cls(
            id=str(tarea.id),
            titulo=tarea.titulo,
            descripcion=tarea.descripcion,
            estado=tarea.estado.value,
            fecha_creacion=tarea.fecha_creacion,  # NUEVO
        )
```

**2. Actualizar el Modelo de Dominio:**

```python
# core/domain/models/tarea.py
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Tarea:
    id: UUID
    titulo: str
    descripcion: str | None
    estado: EstadoTarea
    fecha_creacion: datetime | None = None  # NUEVO
```

**3. MongoDB manejará automáticamente documentos sin el nuevo campo** (esquema flexible).

### Agregar un Nuevo Metodo al Repositorio

**1. Agregar al Port (Interfaz):**

```python
# core/domain/ports/tarea_repository.py

@abstractmethod
def buscar_por_estado(self, estado: EstadoTarea) -> list[Tarea]:
    """Busca tareas por estado."""
    pass
```

**2. Implementar en MongoTareaRepository:**

```python
# infrastructure/mongo/repository/tarea_repository.py

def buscar_por_estado(self, estado: EstadoTarea) -> list[Tarea]:
    """
    Busca todas las tareas con el estado especificado.
    
    Args:
        estado: El estado a buscar.
        
    Returns:
        Lista de tareas con ese estado.
    """
    docs = self.collection.find({"estado": estado.value})
    return [TareaMongo(**doc).to_domain() for doc in docs]
```

### Queries Avanzadas con MongoDB

**Buscar con múltiples criterios:**

```python
from pymongo import ASCENDING, DESCENDING

def buscar_avanzado(
    self,
    texto: str | None = None,
    estados: list[EstadoTarea] | None = None,
    ordenar_por: str = "titulo",
    orden: str = "asc"
) -> list[Tarea]:
    """
    Búsqueda avanzada con filtros y ordenamiento.
    """
    query = {}
    
    if texto:
        # Búsqueda de texto (regex case-insensitive)
        query["$or"] = [
            {"titulo": {"$regex": texto, "$options": "i"}},
            {"descripcion": {"$regex": texto, "$options": "i"}}
        ]
    
    if estados:
        query["estado"] = {"$in": [e.value for e in estados]}
    
    # Ordenamiento
    sort_order = ASCENDING if orden == "asc" else DESCENDING
    
    docs = self.collection.find(query).sort(ordenar_por, sort_order)
    return [TareaMongo(**doc).to_domain() for doc in docs]
```

**Paginacion:**

```python
def list_paginado(
    self,
    page: int = 1,
    per_page: int = 10
) -> tuple[list[Tarea], int]:
    """
    Lista tareas con paginacion.
    
    Returns:
        Tuple de (tareas, total_count)
    """
    skip = (page - 1) * per_page
    
    total = self.collection.count_documents({})
    docs = self.collection.find().skip(skip).limit(per_page)
    
    tareas = [TareaMongo(**doc).to_domain() for doc in docs]
    return tareas, total
```

**Agregaciones:**

```python
def contar_por_estado(self) -> dict[str, int]:
    """
    Cuenta tareas agrupadas por estado.
    
    Returns:
        Diccionario con {estado: cantidad}
    """
    pipeline = [
        {"$group": {
            "_id": "$estado",
            "cantidad": {"$sum": 1}
        }}
    ]
    
    resultados = list(self.collection.aggregate(pipeline))
    return {r["_id"]: r["cantidad"] for r in resultados}
```

### Cambiar a MongoDB Atlas (Nube)

```bash
# Variables de entorno
MONGO_URI=mongodb+srv://usuario:password@cluster0.xxxxx.mongodb.net
MONGO_DB_NAME=mi_proyecto_prod
```

El código automáticamente usará la URI proporcionada.

### Habilitar Indices

```python
# infrastructure/mongo/session/client.py

def init_indexes():
    """Inicializa indices de MongoDB."""
    db = get_db()
    
    # Indice único en id (ya es _id por defecto)
    # Indice en estado para búsquedas frecuentes
    db.tareas.create_index("estado")
    
    # Indice de texto para búsquedas full-text
    db.tareas.create_index([
        ("titulo", "text"),
        ("descripcion", "text")
    ])

# Llamar al iniciar la aplicación
init_indexes()
```

---

## 🔍 Características

### ✅ Esquema Flexible

MongoDB no requiere esquema fijo. Los documentos pueden tener campos opcionales sin necesidad de migraciones.

### ✅ Upsert con update_one

El método `update_one` con `upsert=True` permite:
- Insertar si el documento no existe
- Actualizar si el documento ya existe
- Todo en una sola operación atómica

### ✅ Singleton Pattern

El cliente de MongoDB se crea una sola vez y se reutiliza:

```mermaid
flowchart TD
    A[Primera llamada a get_client] --> B{Cliente existe?}
    B -->|No| C[Crear MongoClient]
    C --> D[Guardar en _client]
    B -->|Si| E[Retornar cliente existente]
    D --> E
```

---

## 🐛 Debugging

### Ver las Queries en la Consola

```python
import logging

# Habilitar logging de pymongo
logging.basicConfig(level=logging.DEBUG)
logging.getLogger('pymongo').setLevel(logging.DEBUG)
```

### Inspeccionar Documentos en MongoDB Shell

```bash
# Conectarse a MongoDB
mongosh

# Ver la base de datos
use mi_proyecto

# Ver las colecciones
show collections

# Ver documentos
db.tareas.find().pretty()

# Contar documentos
db.tareas.countDocuments()

# Ver un documento especifico
db.tareas.findOne({_id: "550e8400-e29b-41d4-a716-446655440000"})
```

### Depurar en Python

```python
def save(self, tarea: Tarea) -> None:
    tarea_mongo = TareaMongo.from_domain(tarea)
    tarea_dict = tarea_mongo.model_dump(by_alias=True)
    
    # Inspeccionar el diccionario
    print(f"Documento a guardar: {tarea_dict}")
    import pdb; pdb.set_trace()  # Punto de interrupción
    
    self.collection.update_one(
        {"_id": tarea_dict["_id"]},
        {"$set": tarea_dict},
        upsert=True
    )
```

---

## ⚠️ Consideraciones

### Sin Transacciones Multi-Documento (por defecto)

A diferencia de SQL, cada operación en MongoDB es atómica a nivel de documento, pero no multi-documento (a menos que uses sesiones explícitas).

Para operaciones que requieren atomicidad multi-documento:

```python
from pymongo import MongoClient

def transferir_datos_atomic(self, origen_id: UUID, destino_id: UUID):
    """Ejemplo de transacción multi-documento."""
    with self.db.client.start_session() as session:
        with session.start_transaction():
            # Todas las operaciones dentro de la transacción
            self.collection.delete_one(
                {"_id": str(origen_id)},
                session=session
            )
            self.collection.update_one(
                {"_id": str(destino_id)},
                {"$set": {"actualizado": True}},
                session=session
            )
            # Si algo falla, todo se revierte
```

### Tamaño Máximo de Documento

MongoDB tiene un límite de **16MB por documento**. Si necesitas almacenar más datos, considera:
- GridFS para archivos grandes
- Normalizar los datos en múltiples colecciones

### Conexiones Concurrentes

El cliente de MongoDB maneja automáticamente un pool de conexiones. Configuración opcional:

```python
from pymongo import MongoClient

_client = MongoClient(
    mongo_uri,
    maxPoolSize=50,      # Máximo de conexiones en el pool
    minPoolSize=10,      # Mínimo de conexiones mantenidas
    maxIdleTimeMS=45000, # Tiempo máximo de inactividad
    waitQueueTimeoutMS=5000,  # Timeout para obtener conexión
)
```

### IDs en MongoDB

Por defecto MongoDB usa `ObjectId` para `_id`. En este proyecto usamos UUIDs como strings para mantener consistencia con el dominio:

```python
# En el modelo
id: str = Field(alias="_id")

# Al guardar
{"_id": str(tarea.id)}  # "550e8400-e29b-41d4-a716-446655440000"
```

---

## 📚 Referencias

- [PyMongo Documentation](https://pymongo.readthedocs.io/)
- [MongoDB Manual](https://docs.mongodb.com/manual/)
- [MongoDB Atlas](https://www.mongodb.com/atlas)
- Arquitectura Hexagonal: Ports & Adapters Pattern

---

**Última actualización:** 2026-02-10
