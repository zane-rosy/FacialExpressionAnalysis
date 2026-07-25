import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_analysis import router as analysis_router
from app.api.routes_health import router as health_router
from app.api.routes_recordings import router as recordings_router
from app.core.config import settings

# Configurar logging para ver el progreso del procesamiento en consola.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
# Reducir el ruido de logs de librerías externas.
logging.getLogger("uvicorn").setLevel(logging.WARNING)
logging.getLogger("matplotlib").setLevel(logging.WARNING)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Backend para analisis facial, AUs, valencia y arousal.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(analysis_router, prefix=settings.api_v1_prefix)
app.include_router(recordings_router, prefix=settings.api_v1_prefix)
