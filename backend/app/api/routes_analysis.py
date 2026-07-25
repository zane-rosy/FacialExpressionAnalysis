from fastapi import APIRouter, File, Query, UploadFile, status

from app.schemas.analysis import AnalysisResponse, VideoAnalysisResponse
from app.services.analysis_orchestrator import AnalysisOrchestrator
from app.services.video_analysis_orchestrator import VideoAnalysisOrchestrator


router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post(
    "/image",
    response_model=AnalysisResponse,
    status_code=status.HTTP_200_OK,
)
async def analyze_image(file: UploadFile = File(...)) -> AnalysisResponse:
    orchestrator = AnalysisOrchestrator()
    return await orchestrator.analyze_image(file)


@router.post(
    "/video",
    response_model=VideoAnalysisResponse,
    status_code=status.HTTP_200_OK,
)
async def analyze_video(
    file: UploadFile = File(...),
    interval_ms: int = Query(500, ge=40, le=5000, description="Intervalo entre frames en milisegundos (mínimo 40ms para soporte 25fps)"),
) -> VideoAnalysisResponse:
    orchestrator = VideoAnalysisOrchestrator()
    return await orchestrator.analyze_video(file, interval_ms=interval_ms)
