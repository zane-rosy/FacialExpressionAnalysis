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


# ─────────────────────────────────────────────────────────────
# Modelos para análisis de video
# ─────────────────────────────────────────────────────────────


class FrameResult(BaseModel):
    """Resultado del análisis de un frame individual dentro de un video."""
    index: int
    timestamp_ms: float = Field(alias="timestampMs")
    analysis: AnalysisResponse

    model_config = ConfigDict(populate_by_name=True)


class VideoSummary(BaseModel):
    """Resumen agregado de todos los frames del video."""
    total_frames: int = Field(alias="totalFrames")
    dominant_emotion: str = Field(alias="dominantEmotion")
    avg_valence: float = Field(alias="avgValence")
    avg_arousal: float = Field(alias="avgArousal")
    valence_timeline: list[float] = Field(alias="valenceTimeline")
    arousal_timeline: list[float] = Field(alias="arousalTimeline")
    dominant_timeline: list[str] = Field(alias="dominantTimeline")
    russell_points: list[RussellPoint] = Field(alias="russellPoints")

    model_config = ConfigDict(populate_by_name=True)


class VideoAnalysisResponse(BaseModel):
    """Respuesta completa del análisis de video."""
    frames: list[FrameResult]
    summary: VideoSummary
    processing: ProcessingMetadata


# ─────────────────────────────────────────────────────────────
# Modelos para grabaciones
# ─────────────────────────────────────────────────────────────


class RecordingSavedResponse(BaseModel):
    """Respuesta al guardar una grabación de webcam."""
    filename: str
    path: str
    label: str = ""
    recorded_at: str = ""


class RecordingAnalysisMetadata(BaseModel):
    avg_valence: float | None = Field(default=None, alias="avgValence")
    avg_arousal: float | None = Field(default=None, alias="avgArousal")
    dominant_emotion: str | None = Field(default=None, alias="dominantEmotion")
    frames_evaluated: int | None = Field(default=None, alias="framesEvaluated")

    model_config = ConfigDict(populate_by_name=True)
