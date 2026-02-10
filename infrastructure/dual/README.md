# Modo Dual - Dual-Write/Dual-Read

## 📖 Descripción

El **DualTareaRepository** implementa un patrón de migración sin downtime que permite escribir y leer desde dos bases de datos simultáneamente (SQLAlchemy y MongoDB).

## 🎯 Objetivo

Facilitar la migración de datos entre diferentes sistemas de persistencia sin interrumpir el servicio, siguiendo las mejores prácticas de la arquitectura hexagonal.

## 🚀 Estrategia de Migración

### Fase 1: Dual-Write (Escritura Doble)
- **save()**: Escribe en **ambas** bases de datos EN PARALELO usando `ThreadPoolExecutor`
- **eliminar()**: Elimina de **ambas** bases de datos EN PARALELO

### Fase 2: Dual-Read (Lectura con Fallback)
- **get()**: Lee de SQLAlchemy (principal), con fallback a MongoDB
- **list()**: Lee de SQLAlchemy (principal), con fallback a MongoDB

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

#### Volver a SQLAlchemy (por defecto):
```powershell
$env:ORM="sqlalchemy"
# o simplemente no definir ORM
```

#### Usar solo MongoDB:
```powershell
$env:ORM="mongo"
```

## 🔍 Características

### ✅ Ejecución Paralela
Las operaciones de escritura se ejecutan en ambas bases de datos simultáneamente usando `ThreadPoolExecutor` con 2 workers:

```python
# Ejemplo interno del código
future_sql = executor.submit(lambda: self._sql_repo.save(tarea))
future_mongo = executor.submit(lambda: self._mongo_repo.save(tarea))
```

### ✅ Tolerancia a Fallos
- Si **una** base de datos falla, la operación continúa con la otra
- Si **ambas** bases de datos fallan, se lanza una excepción
- Los errores se registran con logging detallado

### ✅ Logging Detallado
El repositorio dual incluye emojis y mensajes claros:

```
🔄 Dual-Write iniciado para tarea <uuid>
✓ Operación SQLAlchemy completada
✓ Operación MongoDB completada
✅ Dual-Write exitoso para tarea <uuid>
```

## 🧪 Testing

Puedes probar el modo dual ejecutando los tests:

```powershell
# Test del repositorio dual
pytest test/test_dual_repository.py -v

# Test de todos los repositorios
pytest test/ -v
```

## 📊 Diagrama de Flujo

```
API Request
    ↓
Caso de Uso
    ↓
DualTareaRepository
    ↓
    ├─→ [Thread 1] SQLAlchemy Repository → SQLite/PostgreSQL
    └─→ [Thread 2] MongoDB Repository → MongoDB
    ↓
Espera a que ambos completen (as_completed)
    ↓
Verifica errores y retorna resultado
```

## ⚠️ Consideraciones

### Consistencia Eventual
- Si una base de datos falla temporalmente, los datos pueden quedar inconsistentes
- Se recomienda implementar un proceso de sincronización/reconciliación periódico

### Performance
- El modo dual añade overhead por la ejecución paralela
- Es ideal para migraciones, no como solución permanente

### Transacciones
- Las transacciones NO son atómicas entre ambas bases de datos
- Si necesitas atomicidad completa, considera usar un patrón Saga

## 🔧 Configuración Avanzada

### Personalizar el Repositorio Dual

Puedes inyectar instancias personalizadas de los repositorios:

```python
from infrastructure.dual.repository.tarea_repository import DualTareaRepository
from infrastructure.sqlalchemy.repository.tarea_repository import SqlAlchemyTareaRepository
from infrastructure.mongo.repository.tarea_repository import MongoTareaRepository

# Repositorios personalizados
sql_repo = SqlAlchemyTareaRepository()
mongo_repo = MongoTareaRepository()

# Inyección manual
dual_repo = DualTareaRepository(
    sql_repository=sql_repo,
    mongo_repository=mongo_repo
)
```

## 📚 Referencias

- Ver `roadmap.md` sección 6: "Estrategia de Migración (Dual-Write / Dual-Read)"
- Patrón de Arquitectura Hexagonal: Ports & Adapters
- [Parallel Execution con ThreadPoolExecutor](https://docs.python.org/3/library/concurrent.futures.html)

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

**Última actualización:** 2026-02-10

