from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class ActionUnit(BaseModel):
    """Una unidad de acción con su intensidad de OpenFace y su valor normalizado.

    OpenFace emite intensidades de AU en una escala ordinal de 0-5. La representación
    normalizada divide por 5.0 para mapear a [0, 1] sin perder precisión sobre el valor original.
    """

    raw: float
    normalized: float


class RussellPoint(BaseModel):
    x: float
    y: float
    label: str


class ProcessingMetadata(BaseModel):
    input_type: str = Field(alias="inputType")
    frames_processed: int = Field(alias="framesProcessed")
    mode: str
    notes: list[str]

    model_config = ConfigDict(populate_by_name=True)


class AnalysisResponse(BaseModel):
    dominant_emotion: str = Field(alias="dominantEmotion")
    emotion_probabilities: dict[str, Decimal] = Field(alias="emotionProbabilities")
    action_units: dict[str, ActionUnit] = Field(alias="actionUnits")
    valence: float
    arousal: float
    russell_point: RussellPoint = Field(alias="russellPoint")
    processing: ProcessingMetadata

    model_config = ConfigDict(populate_by_name=True)

    @field_serializer("emotion_probabilities", when_used="json")
    def serialize_emotion_probabilities(self, value: dict[str, Decimal]) -> dict[str, float]:
        """Convierte puntajes Decimal a float para la serialización JSON, preservando precisión."""
        return {k: float(v) for k, v in value.items()}
