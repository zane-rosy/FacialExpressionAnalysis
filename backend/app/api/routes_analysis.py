from fastapi import APIRouter, File, Query, UploadFile, status

from app.schemas.analysis import AnalysisResponse, VideoAnalysisResponse
from app.services.analysis_orchestrator import AnalysisOrchestrator
from app.services.video_analysis_orchestrator import VideoAnalysisOrchestrator
from app.services.stimulus_catalog_service import StimulusCatalogService
from app.services.affective_state_service import AffectiveStateService


router = APIRouter(prefix="/analysis", tags=["analysis"])
stimuli = StimulusCatalogService()
affective_states = AffectiveStateService()


@router.get("/affective-states")
async def affective_states_catalog() -> list[dict[str, object]]:
    return [
        {"name": state.name, "valence": state.valence, "arousal": state.arousal}
        for state in affective_states.get_states()
    ]


@router.get("/stimuli/catalog")
async def stimulus_catalog() -> list[dict[str, object]]:
    return stimuli.catalog()


@router.get("/stimuli/metadata")
async def stimulus_metadata(filename: str) -> dict[str, object] | None:
    return stimuli.lookup(filename)


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
    save_normalized_frames: bool = Query(False, description="Conservar una copia de los frames normalizados para inspección"),
) -> VideoAnalysisResponse:
    orchestrator = VideoAnalysisOrchestrator()
    return await orchestrator.analyze_video(file, interval_ms=interval_ms, save_normalized_frames=save_normalized_frames)
