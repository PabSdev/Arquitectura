from peewee import Model, CharField, TextField, UUIDField
from infrastructure.peewee.session.db import db

class TareaModel(Model):
    id = UUIDField(primary_key=True)
    titulo = CharField()
    descripcion = TextField(null=True)
    estado = CharField()

    class Meta:
        database = db
        table_name = "tareas"
