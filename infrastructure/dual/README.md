# Modo Dual - Dual-Write/Dual-Read

## 📖 Descripción

El **DualTareaRepository** implementa un patrón de migración sin downtime que permite escribir y leer desde dos bases de datos simultáneamente (Peewee/SQL y MongoDB).

Antes de cualquier operación de **escritura**, se realiza un **ping en paralelo** a ambas bases de datos. Si una no responde, se avisa con un warning y la operación se dirige únicamente a la BDD disponible.

## 🎯 Objetivo

Facilitar la migración de datos entre diferentes sistemas de persistencia sin interrumpir el servicio, siguiendo las mejores prácticas de la arquitectura hexagonal.

---

## 🏗️ Arquitectura

### Diagrama de Componentes

```mermaid
graph TB
    A[Application Layer] --> B{Container}
    B -->|ORM=peewee| C[PeeweeTareaRepository]
    B -->|ORM=mongo| D[MongoTareaRepository]
    B -->|ORM=dual| E[DualTareaRepository]

    E --> P["🏓 Ping paralelo (max_workers=4)"]
    P -->|ping_sql| G[(SQL/Postgres)]
    P -->|ping_mongo| H[(MongoDB)]

    P -->|ambas OK| F[Dual-Write paralelo]
    P -->|solo SQL OK| C
    P -->|solo Mongo OK| D
    P -->|ninguna OK| X[❌ Exception]

    F -->|Thread 1| C
    F -->|Thread 2| D
```

### Patrón de Diseño

El repositorio dual implementa el **patrón Adapter** de la arquitectura hexagonal:

```
┌─────────────────────────────────────────────────────────────┐
│                    Application Layer                         │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │ Use Cases    │───▶│  Repository  │◀───│   Domain     │  │
│  │              │    │   Port       │    │   Models     │  │
│  └──────────────┘    └──────┬───────┘    └──────────────┘  │
└─────────────────────────────┼───────────────────────────────┘
                              │
┌─────────────────────────────┼───────────────────────────────┐
│                   Infrastructure Layer                      │
│  ┌──────────────────────────┴────────────────────────────┐ │
│  │              DualTareaRepository                      │ │
│  │  ┌─────────────────┐      ┌────────────────────────┐ │ │
│  │  │  Peewee         │      │  MongoDB               │ │ │
│  │  │  Repository     │      │  Repository            │ │ │
│  │  └────────┬────────┘      └───────────┬────────────┘ │ │
│  └───────────┼───────────────────────────┼──────────────┘ │
└──────────────┼───────────────────────────┼────────────────┘
               │                           │
        ┌──────▼──────┐            ┌───────▼────────┐
        │  SQLite/    │            │    MongoDB     │
        │  PostgreSQL │            │                │
        └─────────────┘            └────────────────┘
```

---

## 🚀 Estrategia de Migración

### Fase 1: Dual-Write con Ping previo

```mermaid
sequenceDiagram
    participant Client
    participant DualRepo as DualTareaRepository
    participant Executor as ThreadPoolExecutor
    participant SQL as Peewee Repo
    participant Mongo as MongoDB Repo

    Client->>DualRepo: save(tarea) / eliminar(id)
    note over DualRepo,Executor: 🏓 Ping en PARALELO (ambas BDD a la vez)
    DualRepo->>Executor: submit(_ping_sql)
    DualRepo->>Executor: submit(_ping_mongo)
    Executor-->>DualRepo: sql_ok, mongo_ok

    alt Ninguna disponible
        DualRepo-->>Client: ❌ Exception inmediata
    else Solo SQL disponible
        DualRepo-->>Client: ⚠️ Warning — guardando solo en SQL
        DualRepo->>SQL: operación
    else Solo Mongo disponible
        DualRepo-->>Client: ⚠️ Warning — guardando solo en MongoDB
        DualRepo->>Mongo: operación
    else Ambas disponibles
        par Escritura dual paralela
            DualRepo->>SQL: operación
            SQL-->>DualRepo: result/error
        and
            DualRepo->>Mongo: operación
            Mongo-->>DualRepo: result/error
        end
        DualRepo-->>Client: ✅ Success (o ⚠️ si una falla en escritura)
    end
```

**Operaciones con ping previo:**
- **save()**: Ping → escribe en BDD disponibles (ambas, una, o falla)
- **eliminar()**: Ping → elimina en BDD disponibles (ambas, una, o falla)

### Fase 2: Dual-Read (Lectura con Fallback)

```mermaid
sequenceDiagram
    participant Client
    participant DualRepo as DualTareaRepository
    participant SQL as Peewee Repo
    participant Mongo as MongoDB Repo
    
    Client->>DualRepo: get(id)
    DualRepo->>SQL: get(id)
    
    alt SQL Success
        SQL-->>DualRepo: tarea
        DualRepo-->>Client: tarea
    else SQL Fail or Not Found
        SQL-->>DualRepo: null/error
        DualRepo->>Mongo: get(id)
        Mongo-->>DualRepo: tarea
        DualRepo-->>Client: tarea
    end
```

**Operaciones:**
- **get()**: Lee de Peewee (principal), con fallback a MongoDB
- **list()**: Lee de Peewee (principal), con fallback a MongoDB

---

## 📋 Uso

### Activar el Modo Dual

Para habilitar el modo dual, configura la variable de entorno `ORM`:

#### Windows PowerShell:
```powershell
$env:ORM="dual"
uvicorn backend_fastapi.main:app --reload
```

#### Linux/Mac:
```bash
export ORM=dual
uvicorn backend_fastapi.main:app --reload
```

### Desactivar el Modo Dual

#### Volver a Peewee (por defecto):
```powershell
$env:ORM="peewee"
# o simplemente no definir ORM
```

#### Usar solo MongoDB:
```powershell
$env:ORM="mongo"
```

---

## 🔍 Características

### ✅ Ping paralelo previo a escrituras

Antes de cada `save()` o `eliminar()`, se hace ping en paralelo a ambas BDD. La latencia del ping = `max(ping_sql, ping_mongo)` en lugar de la suma:

```python
# Pings en paralelo — no suma latencias, solo espera el más lento
future_sql   = executor.submit(_ping_sql)
future_mongo = executor.submit(_ping_mongo)
sql_ok       = future_sql.result(timeout=4)
mongo_ok     = future_mongo.result(timeout=4)
```

### ✅ Ejecución Paralela con pool ampliado

El pool ahora tiene **4 workers**: 2 para pings y 2 para operaciones reales, evitando que los pings bloqueen las escrituras:

```python
# Pool de threads global — 4 workers (antes 2)
executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="DualRepo")
```

### ✅ Imports a nivel de módulo

`psycopg` y `MongoClient` se importan **una sola vez** al arrancar el módulo (no en cada llamada a `_ping_sql`/`_ping_mongo`), eliminando el overhead repetido de import:

### ✅ Tolerancia a Fallos con dispatch condicional

```mermaid
flowchart TD
    A[save / eliminar] --> P["🏓 Ping paralelo"]
    P --> B{sql_ok}
    P --> C{mongo_ok}

    B -- No --> OnlyMongo{mongo_ok?}
    B -- Sí --> BothCheck{mongo_ok?}

    OnlyMongo -- Sí --> M["⚠️ Solo MongoDB"]
    OnlyMongo -- No --> X["❌ Exception inmediata"]

    BothCheck -- No --> S["⚠️ Solo SQL"]
    BothCheck -- Sí --> Dual["🔄 Dual-Write paralelo"]

    Dual --> R{Resultado escritura}
    R -->|Ambos OK| OK["✅ Success"]
    R -->|Uno OK| W["⚠️ Warning"]
    R -->|Ambos Fail| E["❌ Exception"]
```

- Si **ninguna** BDD hace ping → excepción **inmediata** (sin intentar escribir)
- Si **solo una** BDD hace ping → avisa con `⚠️ warning` y escribe en la disponible
- Si **ambas** hacen ping → escritura dual en paralelo
- Los errores se registran con logging detallado

### ✅ Logging Detallado

El repositorio dual incluye emojis y mensajes claros para facilitar el debugging:

```
🏓 Ping previo a BDD para save de <uuid>...
🔴 Mongo no disponible: <error>          ← BDD caída
⚠️ MongoDB no disponible. save de <uuid> se guardará SOLO en SQL.
✓ Operación Peewee (solo) completada

# Cuando ambas están OK:
🏓 Ping previo a BDD para save de <uuid>...
🔄 save dual iniciado para <uuid>
✓ Operación Peewee completada
✓ Operación MongoDB completada
✅ save dual exitoso para <uuid>
```

**Niveles de Log:**
- `INFO`: Inicio/completado de operaciones dual
- `WARNING`: Una BDD no disponible (ping) o falló en escritura
- `ERROR`: Ninguna BDD disponible, o ambas fallaron en escritura
- `DEBUG`: Operaciones individuales completadas

---

## 🧪 Testing

Puedes probar el modo dual ejecutando los tests:

```powershell
# Test del repositorio dual
pytest test/test_dual_repository.py -v

# Test de todos los repositorios
pytest test/ -v
```

---

## ⚠️ Consideraciones

### Consistencia Eventual

- Si una base de datos falla temporalmente, los datos pueden quedar inconsistentes
- Se recomienda implementar un proceso de sincronización/reconciliación periódico

### Performance

- El modo dual añade overhead por la ejecución paralela
- Es ideal para migraciones, no como solución permanente
- El tiempo de respuesta es el tiempo del repositorio más lento + overhead del threading

### Transacciones

- Las transacciones NO son atómicas entre ambas bases de datos
- Si necesitas atomicidad completa, considera usar un patrón Saga
- Cada repositorio maneja sus propias transacciones independientemente

---

## 🔧 Configuración Avanzada

### Personalizar el Repositorio Dual

Puedes inyectar instancias personalizadas de los repositorios:

```python
from infrastructure.dual.repository.tarea_repository import DualTareaRepository
from infrastructure.peewee.repository.tarea_repository import PeeweeTareaRepository
from infrastructure.mongo.repository.tarea_repository import MongoTareaRepository

# Repositorios personalizados
sql_repo = PeeweeTareaRepository()
mongo_repo = MongoTareaRepository()

# Inyección manual
dual_repo = DualTareaRepository(
    sql_repository=sql_repo,
    mongo_repository=mongo_repo
)
```

### Ajustar el ThreadPoolExecutor

El executor se define como variable global en `tarea_repository.py`. Actualmente usa **4 workers**: 2 reservados para los pings paralelos y 2 para las operaciones reales:

```python
# Pool con 4 workers — ajustar si hay más concurrencia
executor = ThreadPoolExecutor(
    max_workers=4,  # 2 pings + 2 operaciones
    thread_name_prefix="DualRepo"
)
```

### Ajustar timeouts de ping

Los timeouts se configuran como constantes al inicio del módulo:

```python
_PING_TIMEOUT_SECS = 3   # timeout para psycopg (Postgres)
_PING_TIMEOUT_MS   = 3000  # timeout para MongoClient
```

---

## 🛠️ Guía para Realizar Cambios

### Estructura de Archivos

```
infrastructure/
└── dual/
    ├── repository/
    │   └── tarea_repository.py    # ← Archivo principal
    └── README.md                   # ← Este archivo
```

### Agregar Nuevos Métodos al Repositorio

Si necesitas agregar nuevos métodos al `TareaRepository` y hacerlos compatibles con el modo dual:

**1. Agregar al Port (Interfaz):**
```python
# core/domain/ports/tarea_repository.py
class TareaRepository(ABC):
    @abstractmethod
    def nuevo_metodo(self, tarea_id: UUID) -> Tarea:
        pass
```

**2. Implementar en Repositorios Base:**
```python
# infrastructure/peewee/repository/tarea_repository.py
class PeeweeTareaRepository(TareaRepository):
    def nuevo_metodo(self, tarea_id: UUID) -> Tarea:
        # Implementación Peewee
        pass

# infrastructure/mongo/repository/tarea_repository.py
class MongoTareaRepository(TareaRepository):
    def nuevo_metodo(self, tarea_id: UUID) -> Tarea:
        # Implementación MongoDB
        pass
```

**3. Implementar en DualTareaRepository:**

**Para operaciones de escritura (con ping previo):**
```python
def nuevo_metodo_write(self, tarea: Tarea) -> None:
    """Operación de escritura dual con ping previo."""
    self._dispatch_escritura(
        operacion="nuevo_metodo_write",
        sql_func=lambda: self._sql_repo.nuevo_metodo_write(tarea),
        mongo_func=lambda: self._mongo_repo.nuevo_metodo_write(tarea),
        entidad_id=tarea.id,
    )
```

El método `_dispatch_escritura` se encarga del ping, dispatch condicional y logging automáticamente.

**Para operaciones de lectura (Dual-Read):**
```python
def nuevo_metodo_read(self, tarea_id: UUID) -> Tarea | None:
    """Operación de lectura con fallback."""
    logger.debug(f"🔍 Buscando tarea {tarea_id}")
    
    # Intenta leer de Peewee primero
    try:
        result = self._sql_repo.nuevo_metodo_read(tarea_id)
        if result is not None:
            return result
    except Exception as e:
        logger.warning(f"⚠️ Error en Peewee: {e}")
    
    # Fallback a MongoDB
    try:
        result = self._mongo_repo.nuevo_metodo_read(tarea_id)
        if result is not None:
            logger.info(f"✓ Obtenido de MongoDB (fallback)")
            return result
    except Exception as e:
        logger.error(f"❌ Error en MongoDB: {e}")
    
    return None
```

### Modificar el Comportamiento del ThreadPool

Para cambiar el número de workers o el comportamiento del executor:

```python
# Linea 16 en tarea_repository.py
# Opción 1: Más workers para mayor concurrencia
executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="DualRepo")

# Opción 2: Usar ProcessPoolExecutor para operaciones CPU-bound
from concurrent.futures import ProcessPoolExecutor
executor = ProcessPoolExecutor(max_workers=2)
```

### Cambiar la Estrategia de Fallback

Para modificar cuál repositorio es el "primario":

```python
def get(self, tarea_id: UUID) -> Tarea | None:
    # Cambiar el orden de los intentos
    try:
        # Intentar MongoDB primero
        tarea = self._mongo_repo.get(tarea_id)
        if tarea is not None:
            return tarea
    except Exception as e:
        logger.warning(f"⚠️ Error en MongoDB: {e}")
    
    # Fallback a Peewee
    try:
        tarea = self._sql_repo.get(tarea_id)
        if tarea is not None:
            logger.info(f"✓ Obtenido de Peewee (fallback)")
            return tarea
    except Exception as e:
        logger.warning(f"⚠️ Error en Peewee: {e}")
    
    return None
```

### Agregar Métricas/Monitoreo

Para agregar métricas de rendimiento:

```python
import time
from prometheus_client import Counter, Histogram

# Métricas
dual_write_duration = Histogram(
    'dual_write_duration_seconds',
    'Duration of dual-write operations',
    ['repository']
)
dual_write_errors = Counter(
    'dual_write_errors_total',
    'Total errors in dual-write operations',
    ['repository', 'error_type']
)

def save(self, tarea: Tarea) -> None:
    start_time = time.time()
    
    _, sql_error, _, mongo_error = self._execute_parallel(...)
    
    # Registrar métricas
    dual_write_duration.labels(repository='sql').observe(time.time() - start_time)
    dual_write_duration.labels(repository='mongo').observe(time.time() - start_time)
    
    if sql_error:
        dual_write_errors.labels(repository='sql', error_type=type(sql_error).__name__).inc()
    if mongo_error:
        dual_write_errors.labels(repository='mongo', error_type=type(mongo_error).__name__).inc()
```

---

## 🐛 Debugging y Troubleshooting

### Logs no aparecen

Asegúrate de que el logging esté configurado correctamente:

```python
import logging

# Configurar nivel de logging
logging.basicConfig(
    level=logging.DEBUG,  # Cambiar a INFO en producción
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### Timeouts en operaciones paralelas

El `ThreadPoolExecutor` no tiene timeout por defecto. Para agregar:

```python
from concurrent.futures import wait, FIRST_COMPLETED

# En _execute_parallel
future_sql = executor.submit(sql_func)
future_mongo = executor.submit(mongo_func)

# Esperar con timeout
done, not_done = wait(
    [future_sql, future_mongo],
    timeout=10.0,  # 10 segundos
    return_when=FIRST_COMPLETED
)

if not_done:
    # Cancelar las que no terminaron
    for future in not_done:
        future.cancel()
```

### Deadlocks

Si hay deadlocks:
1. Verificar que los repositorios base no compartan recursos
2. Asegurar que no haya locks anidados entre SQLAlchemy y MongoDB
3. Considerar usar `asyncio` en lugar de threads si hay mucha I/O

---

## 📚 Referencias

- Ver `roadmap.md` sección 6: "Estrategia de Migración (Dual-Write / Dual-Read)"
- Patrón de Arquitectura Hexagonal: Ports & Adapters
- [Parallel Execution con ThreadPoolExecutor](https://docs.python.org/3/library/concurrent.futures.html)

---

## 🎓 Ejemplo Completo

```python
# 1. Configurar variable de entorno
import os
os.environ["ORM"] = "dual"

# 2. Obtener el caso de uso (automáticamente usará DualTareaRepository)
from infrastructure.container import get_crear_tarea_use_case
from core.application.crear_tarea import CrearTareaCommand
from core.domain.models.tarea import EstadoTarea

use_case = get_crear_tarea_use_case()

# 3. Ejecutar operación - se escribirá en AMBAS bases de datos
cmd = CrearTareaCommand(
    titulo="Tarea de prueba",
    descripcion="Esta tarea se guardará en SQLite Y MongoDB",
    estado=EstadoTarea.PENDIENTE
)

tarea = use_case.execute(cmd)
print(f"Tarea {tarea.id} creada en ambas bases de datos")
```

---

**Última actualización:** 2026-02-21 — Ping paralelo previo a escrituras, imports a nivel de módulo, pool ampliado a 4 workers, dispatch condicional por disponibilidad de BDD.
