from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_analysis import router as analysis_router
from app.api.routes_health import router as health_router
from app.core.config import settings


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
