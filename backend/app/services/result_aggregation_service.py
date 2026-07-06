from app.schemas.analysis import (
    ActionUnit,
    AnalysisResponse,
    ProcessingMetadata,
    RussellPoint,
)

# OpenFace emite intensidades de AU en una escala ordinal de 0-5. 
# Normalizamos dividiendo por este máximo para obtener un valor en [0, 1] sin pérdida de información.
AU_INTENSITY_MAX = 5.0


class ResultAggregationService:
    """Consolida los resultados individuales de análisis en un solo :class:`AnalysisResponse`.

    Responsabilidades:
    - Recibir salidas de EmotionAnalysisService, OpenFaceService y
      ValenceArousalService.
    - Construir los sub-modelos RussellPoint y ProcessingMetadata.
    - Retornar un AnalysisResponse completamente poblado.
    """

    def consolidate_image(
        self,
        emotion_result: dict[str, object],
        au_result: dict[str, float],
        affect_result: dict[str, float],
    ) -> AnalysisResponse:
        """Construye y retorna un :class:`AnalysisResponse` a partir de los tres sub-resultados.

        Parameters
        ----------
        emotion_result:
            Salida de EmotionAnalysisService.analyze_image — debe contener
            ``dominant_emotion`` (str) y ``emotion_probabilities`` (dict).
        au_result:
            Salida de OpenFaceService.analyze_image — nombre de AU a valor de
            intensidad (escala 0-5 de OpenFace).
        affect_result:
            Salida de ValenceArousalService.compute — debe contener
            ``valence`` y ``arousal`` (float).

        Returns
        -------
        AnalysisResponse
            Modelo de respuesta completo listo para serializar.
        """
        dominant_emotion: str = emotion_result["dominant_emotion"]  # type: ignore[assignment]
        emotion_probabilities: dict[str, float] = emotion_result["emotion_probabilities"]  # type: ignore[assignment]
        valence: float = affect_result["valence"]
        arousal: float = affect_result["arousal"]

        action_units: dict[str, ActionUnit] = {
            name: ActionUnit(
                raw=raw_value,
                normalized=raw_value / AU_INTENSITY_MAX,
            )
            for name, raw_value in au_result.items()
        }

        return AnalysisResponse(
            dominantEmotion=dominant_emotion,
            emotionProbabilities=emotion_probabilities,
            actionUnits=action_units,
            valence=valence,
            arousal=arousal,
            russellPoint=RussellPoint(
                x=valence,
                y=arousal,
                label=dominant_emotion,
            ),
            processing=ProcessingMetadata(
                inputType="image",
                framesProcessed=1,
                mode="real",
                notes=[
                    "Puntajes de emociones de los clasificadores de regresión logística de API_Emotion_Recognition.",
                    "Valores de AU de OpenFace FaceLandmarkImg.",
                    "Valencia y arousal calculados a partir de las salidas reales de los clasificadores.",
                ],
            ),
        )
