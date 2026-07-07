from fastapi import HTTPException, UploadFile, status

from app.schemas.analysis import AnalysisResponse
from app.services.emotion_service import EmotionAnalysisService
from app.services.openface_service import OpenFaceService
from app.services.result_aggregation_service import ResultAggregationService
from app.services.temp_file_service import TemporaryFileService
from app.services.valence_arousal_service import ValenceArousalService


class AnalysisOrchestrator:
    def __init__(self) -> None:
        self.temp_file_service = TemporaryFileService()
        self.emotion_service = EmotionAnalysisService()
        self.openface_service = OpenFaceService()
        self.valence_arousal_service = ValenceArousalService()
        self.result_aggregation_service = ResultAggregationService()

    async def analyze_image(self, file: UploadFile) -> AnalysisResponse:
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File name is required.",
            )

        temporary_image = await self.temp_file_service.create_upload_copy(file)

        try:
            emotion_result = self.emotion_service.analyze_image(temporary_image.path)
            au_result = self.openface_service.analyze_image(temporary_image.path)
            affect_result = self.valence_arousal_service.compute(
                emotion_probabilities=emotion_result["emotion_probabilities"],  # type: ignore[arg-type]
                action_units=au_result,
            )

            return self.result_aggregation_service.consolidate_image(
                emotion_result=emotion_result,
                au_result=au_result,
                affect_result=affect_result,
            )
        finally:
            self.temp_file_service.cleanup(temporary_image.path)
