import os

import uvicorn
from dotenv import load_dotenv

load_dotenv()


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def run() -> None:
    host = os.getenv("HOST", "127.0.0.1")
    port_str = os.getenv("PORT", "8000")
    port = int(port_str)
    reload = _as_bool(os.getenv("RELOAD", "true"))
    log_level = os.getenv("LOG_LEVEL", "info")

    print(f"Starting server at http://{host}:{port} (Reload: {reload})")

    uvicorn.run(
        "backend_fastapi.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
    )


if __name__ == "__main__":
    run()
