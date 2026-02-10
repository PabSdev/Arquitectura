from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend_fastapi.api.routes.tareas import router as tareas_router

app = FastAPI(title="Arquitectura Mejorada API")

# Configure CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tareas_router)
