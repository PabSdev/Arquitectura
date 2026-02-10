from core.application.crear_tarea import CrearTareaUseCase
from infrastructure.container import get_crear_tarea_use_case

from core.application.editar_tarea import EditarTareaUseCase
from infrastructure.container import get_editar_tarea_use_case

from core.application.eliminar_tarea import EliminarTareaUseCase
from infrastructure.container import get_eliminar_tarea_use_case

from core.application.listar_tareas import ListarTareasUseCase
from infrastructure.container import get_listar_tareas_use_case


def crear_tarea_use_case() -> CrearTareaUseCase:
    return get_crear_tarea_use_case()


def editar_tarea_use_case() -> EditarTareaUseCase:
    return get_editar_tarea_use_case()


def eliminar_tarea_use_case() -> EliminarTareaUseCase:
    return get_eliminar_tarea_use_case()


def listar_tareas_use_case() -> ListarTareasUseCase:
    return get_listar_tareas_use_case()
