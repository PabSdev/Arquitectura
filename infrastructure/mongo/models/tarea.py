from uuid import UUID

from pydantic import BaseModel, Field

from core.domain.models.tarea import EstadoTarea, Tarea


class TareaMongo(BaseModel):
    """
    Modelo de Tarea para MongoDB.
    Representa cómo se almacena la tarea en la base de datos.
    """

    id: str = Field(alias="_id")
    titulo: str
    descripcion: str | None = None
    estado: str

    model_config = {"populate_by_name": True}

    def to_domain(self) -> Tarea:
        """
        Convierte el modelo de MongoDB al modelo de dominio.

        Retorna:
            Tarea: La entidad de dominio.
        """
        return Tarea(
            id=UUID(self.id),
            titulo=self.titulo,
            descripcion=self.descripcion,
            estado=EstadoTarea(self.estado),
        )

    @classmethod
    def from_domain(cls, tarea: Tarea) -> "TareaMongo":
        """
        Crea una instancia de TareaMongo a partir de una entidad de dominio.

        Argumentos:
            tarea (Tarea): La entidad de dominio.

        Retorna:
            TareaMongo: El modelo de MongoDB.
        """
        return cls(
            id=str(tarea.id),
            titulo=tarea.titulo,
            descripcion=tarea.descripcion,
            estado=tarea.estado.value,
        )
