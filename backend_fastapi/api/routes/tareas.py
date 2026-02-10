from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from core.domain.models.tarea import Tarea

from backend_fastapi.api.deps import (
    crear_tarea_use_case,
    editar_tarea_use_case,
    eliminar_tarea_use_case,
    listar_tareas_use_case,
)
from core.application.crear_tarea import CrearTareaCommand, CrearTareaUseCase
from core.application.editar_tarea import EditarTareaCommand, EditarTareaUseCase
from core.application.eliminar_tarea import EliminarTareaUseCase
from core.application.listar_tareas import ListarTareasUseCase

router = APIRouter(prefix="/tareas", tags=["tareas"])


@router.post(
    "",
    response_model=Tarea,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una nueva tarea",
)
def crear_tarea(
    cmd: CrearTareaCommand,
    use_case: CrearTareaUseCase = Depends(crear_tarea_use_case),
) -> Tarea:
    """
    Crea una nueva tarea en el sistema.

    - **titulo**: Título de la tarea.
    - **descripcion**: Descripción opcional de la tarea.
    - **estado**: Estado inicial de la tarea (por defecto PENDIENTE).
    """
    return use_case.execute(cmd)


@router.get(
    "",
    response_model=list[Tarea],
    summary="Listar todas las tareas",
)
def listar_tareas(
    use_case: ListarTareasUseCase = Depends(listar_tareas_use_case),
) -> list[Tarea]:
    """
    Obtiene una lista de todas las tareas registradas.
    """
    return use_case.execute()


@router.put(
    "/{tarea_id}",
    response_model=Tarea,
    summary="Editar una tarea existente",
)
def editar_tarea(
    tarea_id: UUID,
    cmd: EditarTareaCommand,
    use_case: EditarTareaUseCase = Depends(editar_tarea_use_case),
) -> Tarea:
    """
    Modifica los datos de una tarea existente.

    - **tarea_id**: UUID de la tarea a modificar.
    - **titulo**: Nuevo título.
    - **descripcion**: Nueva descripción.
    - **estado**: Nuevo estado.
    """
    try:
        return use_case.execute(tarea_id, cmd)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/{tarea_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar una tarea",
)
def eliminar_tarea(
    tarea_id: UUID,
    use_case: EliminarTareaUseCase = Depends(eliminar_tarea_use_case),
) -> None:
    """
    Elimina una tarea del sistema.

    - **tarea_id**: UUID de la tarea a eliminar.
    """
    use_case.execute(tarea_id)
