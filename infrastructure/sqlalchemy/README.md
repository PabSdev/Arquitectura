# SQLAlchemy Infrastructure

## 📖 Descripción

Implementación del repositorio de tareas usando **SQLAlchemy** como ORM. Este módulo proporciona la capa de persistencia para bases de datos relacionales (SQLite, PostgreSQL, MySQL, etc.) siguiendo los principios de la arquitectura hexagonal.

## 🎯 Objetivo

Proporcionar una implementación robusta y eficiente del puerto `TareaRepository` usando SQLAlchemy, manteniendo la separación entre el dominio y la infraestructura.

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
    
    subgraph "Infrastructure Layer - SQLAlchemy"
        Repo[SqlAlchemyTareaRepository]
        Model[TareaModel]
        Session[Session Management]
        DB[(Database Engine)]
        
        Repo -->|usa| Session
        Session -->|conecta| DB
        Repo -->|mapea| Model
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
    participant Repo as SqlAlchemyTareaRepository
    participant Session as SQLAlchemy Session
    participant Model as TareaModel
    participant DB as Database
    
    UseCase->>Repo: save(tarea)
    Repo->>Repo: init_db()
    Repo->>Session: get_session()
    Session-->>Repo: session
    
    Repo->>Model: TareaModel(...)
    Model-->>Repo: tarea_model
    
    Repo->>Session: merge(tarea_model)
    Repo->>Session: commit()
    Session->>DB: INSERT/UPDATE
    DB-->>Session: ok
    Session-->>Repo: committed
    Repo-->>UseCase: return
    
    Note over Repo,Session: finally: session.close()
```

---

## 📁 Estructura de Archivos

```
infrastructure/sqlalchemy/
├── __init__.py
├── session/
│   ├── __init__.py
│   └── db.py              # Configuración de conexión y sesiones
├── model/
│   ├── __init__.py
│   └── models.py          # Modelos SQLAlchemy (ORM)
└── repository/
    ├── __init__.py
    └── tarea_repository.py # Implementación del repositorio
```

---

## 🔧 Configuración

### Variables de Entorno

```bash
# URL de conexión a la base de datos
DATABASE_URL=sqlite:///./test.db
# Para PostgreSQL:
# DATABASE_URL=postgresql://user:password@localhost:5432/dbname
# Para MySQL:
# DATABASE_URL=mysql+pymysql://user:password@localhost:3306/dbname
```

### Configuración del Motor

```python
# infrastructure/sqlalchemy/session/db.py
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}  # Solo para SQLite
    if DATABASE_URL.startswith("sqlite")
    else {},
)
```

---

## 🚀 Uso

### Inicializar la Base de Datos

```python
from infrastructure.sqlalchemy.session.db import init_db

# Crea todas las tablas si no existen
init_db()
```

### Usar el Repositorio

```python
from uuid import uuid4
from infrastructure.sqlalchemy.repository.tarea_repository import SqlAlchemyTareaRepository
from core.domain.models.tarea import Tarea, EstadoTarea

# Crear instancia del repositorio
repo = SqlAlchemyTareaRepository()

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
os.environ["ORM"] = "sqlalchemy"

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
# Tests específicos de SQLAlchemy
pytest test/test_sqlalchemy_repository.py -v

# Tests de integración
pytest test/test_integration.py -v
```

### Base de Datos de Test

Para usar una base de datos en memoria para tests:

```python
# En tu archivo de test o conftest.py
import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from infrastructure.sqlalchemy.session.db import init_db

@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    yield
    # La BD en memoria se destruye automáticamente
```

---

## 📝 Modelo de Datos

### TareaModel

```python
class TareaModel(Base):
    __tablename__ = "tareas"
    
    id = Column(String, primary_key=True, index=True)
    titulo = Column(String, nullable=False)
    descripcion = Column(Text, nullable=True)
    estado = Column(String, nullable=False)
```

### Mapeo Domain <-> Model

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

## 🛠️ Guía para Desarrolladores

### Agregar un Nuevo Campo a Tarea

**1. Actualizar el Modelo SQLAlchemy:**

```python
# infrastructure/sqlalchemy/model/models.py
from sqlalchemy import Column, String, Text, DateTime
from datetime import datetime

class TareaModel(Base):
    __tablename__ = "tareas"
    
    id = Column(String, primary_key=True, index=True)
    titulo = Column(String, nullable=False)
    descripcion = Column(Text, nullable=True)
    estado = Column(String, nullable=False)
    fecha_creacion = Column(DateTime, default=datetime.utcnow)  # NUEVO
```

**2. Actualizar el Mapeo en el Repositorio:**

```python
# infrastructure/sqlalchemy/repository/tarea_repository.py

def save(self, tarea: Tarea) -> None:
    session = get_session()
    try:
        tarea_model = TareaModel(
            id=str(tarea.id),
            titulo=tarea.titulo,
            descripcion=tarea.descripcion,
            estado=tarea.estado.value,
            fecha_creacion=tarea.fecha_creacion,  # NUEVO
        )
        session.merge(tarea_model)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def get(self, tarea_id: UUID) -> Tarea | None:
    session = get_session()
    try:
        tarea_model = session.get(TareaModel, str(tarea_id))
        if tarea_model is None:
            return None
        
        return Tarea(
            id=UUID(tarea_model.id),
            titulo=tarea_model.titulo,
            descripcion=tarea_model.descripcion,
            estado=EstadoTarea(tarea_model.estado),
            fecha_creacion=tarea_model.fecha_creacion,  # NUEVO
        )
    finally:
        session.close()
```

**3. Actualizar el Modelo de Dominio (si es necesario):**

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

### Agregar un Nuevo Método al Repositorio

**1. Agregar al Port (Interfaz):**

```python
# core/domain/ports/tarea_repository.py

@abstractmethod
def buscar_por_estado(self, estado: EstadoTarea) -> list[Tarea]:
    """Busca tareas por estado."""
    pass
```

**2. Implementar en SqlAlchemyTareaRepository:**

```python
# infrastructure/sqlalchemy/repository/tarea_repository.py

def buscar_por_estado(self, estado: EstadoTarea) -> list[Tarea]:
    """
    Busca todas las tareas con el estado especificado.
    
    Args:
        estado: El estado a buscar.
        
    Returns:
        Lista de tareas con ese estado.
    """
    session = get_session()
    try:
        tarea_models = session.query(TareaModel).filter(
            TareaModel.estado == estado.value
        ).all()
        
        return [
            Tarea(
                id=UUID(tarea_model.id),
                titulo=tarea_model.titulo,
                descripcion=tarea_model.descripcion,
                estado=EstadoTarea(tarea_model.estado),
            )
            for tarea_model in tarea_models
        ]
    finally:
        session.close()
```

### Cambiar a PostgreSQL

```python
# .env o variables de entorno
DATABASE_URL=postgresql://username:password@localhost:5432/mi_base_de_datos
```

El código automáticamente detecta que no es SQLite y omite el parámetro `check_same_thread`.

### Implementar Transacciones Complejas

```python
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager

@contextmanager
def transactional_session():
    """Context manager para transacciones complejas."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

# Uso
def transferir_datos(self, tarea_origen_id: UUID, tarea_destino_id: UUID) -> None:
    with transactional_session() as session:
        origen = session.get(TareaModel, str(tarea_origen_id))
        destino = session.get(TareaModel, str(tarea_destino_id))
        
        # Operaciones atómicas
        destino.descripcion = origen.descripcion
        session.delete(origen)
        # Si falla algo, todo se hace rollback
```

### Usar Queries Avanzadas

```python
from sqlalchemy import or_, and_

def buscar_avanzado(
    self, 
    texto: str | None = None, 
    estados: list[EstadoTarea] | None = None
) -> list[Tarea]:
    session = get_session()
    try:
        query = session.query(TareaModel)
        
        if texto:
            query = query.filter(
                or_(
                    TareaModel.titulo.ilike(f"%{texto}%"),
                    TareaModel.descripcion.ilike(f"%{texto}%")
                )
            )
        
        if estados:
            estado_values = [e.value for e in estados]
            query = query.filter(TareaModel.estado.in_(estado_values))
        
        tarea_models = query.all()
        return [...]  # Mapear a dominio
    finally:
        session.close()
```

---

## 🔍 Características

### ✅ Manejo de Sesiones

Cada operación del repositorio:
1. Obtiene una nueva sesión
2. Ejecuta la operación
3. Cierra la sesión en el bloque `finally`

Esto garantiza que no haya fugas de conexiones.

### ✅ Transacciones

```mermaid
flowchart TD
    A[Iniciar Operación] --> B[Obtener Sesión]
    B --> C[Ejecutar Operación]
    C --> D{¿Error?}
    D -->|No| E[Commit]
    D -->|Sí| F[Rollback]
    F --> G[Re-lanzar Excepción]
    E --> H[Cerrar Sesión]
    G --> H
    H --> I[Fin]
```

### ✅ Upsert con merge()

El método `session.merge()` permite:
- Insertar si el registro no existe
- Actualizar si el registro ya existe
- Manejar automáticamente el estado de la sesión

---

## 🐛 Debugging

### Ver Queries SQL Generados

```python
# Habilitar logging de SQL
import logging

logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

# Ahora verás todas las queries en la consola
repo.list()
# INFO:sqlalchemy.engine.Engine:SELECT tareas.id, tareas.titulo...
```

### Depurar en PDB

```python
def save(self, tarea: Tarea) -> None:
    session = get_session()
    try:
        tarea_model = TareaModel(...)
        import pdb; pdb.set_trace()  # Punto de interrupción
        session.merge(tarea_model)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

### Ver el Esquema Actual

```python
from infrastructure.sqlalchemy.session.db import engine, Base

# Ver todas las tablas
print(Base.metadata.tables.keys())

# Ver el esquema SQL
from sqlalchemy.schema import CreateTable
print(CreateTable(TareaModel.__table__).compile(engine))
```

---

## ⚠️ Consideraciones

### Session Thread Safety

Las sesiones de SQLAlchemy **NO son thread-safe**. Cada thread debe tener su propia sesión:

```python
# CORRECTO: Cada thread obtiene su propia sesión[__init__.py](__init__.py)
def save(self, tarea: Tarea) -> None:
    session = get_session()  # Nueva sesión por llamada
    # ... operaciones ...
    session.close()

# INCORRECTO: Compartir sesión entre threads
class Repo:
    def __init__(self):
        self.session = get_session()  # ❌ Mala práctica
```

### Migraciones

Para manejar migraciones de esquema, considera usar **Alembic**:

```bash
# Instalar Alembic
pip install alembic

# Inicializar
alembic init alembic

# Crear migración
alembic revision --autogenerate -m "agregar campo fecha"

# Aplicar migración
alembic upgrade head
```

---

## 📚 Referencias

- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [SQLAlchemy ORM Tutorial](https://docs.sqlalchemy.org/en/14/orm/tutorial.html)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- Arquitectura Hexagonal: Ports & Adapters Pattern

---

**Última actualización:** 2026-02-10
