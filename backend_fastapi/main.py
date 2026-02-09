from fastapi import FastAPI

from backend_fastapi.api.routes.tareas import router as tareas_router

app = FastAPI(title="Arquitectura Mejorada API")
app.include_router(tareas_router)
