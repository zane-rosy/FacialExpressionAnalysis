from fastapi import APIRouter, File, UploadFile, status

from app.schemas.analysis import AnalysisResponse
from app.services.analysis_orchestrator import AnalysisOrchestrator


router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post(
    "/image",
    response_model=AnalysisResponse,
    status_code=status.HTTP_200_OK,
)
async def analyze_image(file: UploadFile = File(...)) -> AnalysisResponse:
    orchestrator = AnalysisOrchestrator()
    return await orchestrator.analyze_image(file)
