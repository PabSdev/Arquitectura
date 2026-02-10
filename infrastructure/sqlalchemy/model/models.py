from sqlalchemy import Column, String, Text
from infrastructure.sqlalchemy.session.db import Base


class TareaModel(Base):
    __tablename__ = "tareas"

    id = Column(String, primary_key=True, index=True)
    titulo = Column(String, nullable=False)
    descripcion = Column(Text, nullable=True)
    estado = Column(String, nullable=False)
