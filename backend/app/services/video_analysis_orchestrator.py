import logging
import re
import time
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings
from app.schemas.analysis import (
    AnalysisResponse,
    FrameResult,
    ProcessingMetadata,
    VideoAnalysisResponse,
    VideoSummary,
)
from app.services.emotion_service import EmotionAnalysisService
from app.services.face_normalization_service import FaceNormalizationService
from app.services.frame_extraction_service import FrameCapture, FrameExtractionService
from app.services.openface_service import OpenFaceService
from app.services.result_aggregation_service import ResultAggregationService
from app.services.temp_file_service import TemporaryFileService
from app.services.valence_arousal_service import ValenceArousalService

logger = logging.getLogger(__name__)


class VideoAnalysisOrchestrator:
    """Orquesta el pipeline de análisis para un archivo de video.

    Pipeline:
    1. Guardar el video subido como archivo temporal.
    2. Extraer frames a un directorio temporal compartido con FrameExtractionService.
    3. Ejecutar OpenFace una sola vez vía analyze_frame_directory() → retorna {índice_frame: mapa_AU}.
    4. Para cada frame extraído cuyo índice esté en el mapa de AU: ejecutar EmotionAnalysisService
       y ValenceArousalService, luego agregar.
    5. Los frames sin datos de AU o rechazados por el predictor emocional se omiten.
    6. Construir resumen a partir de los frames supervivientes y retornar VideoAnalysisResponse.
    """

    def __init__(self) -> None:
        self.temp_file_service = TemporaryFileService()
        self.frame_extraction_service = FrameExtractionService()
        self.emotion_service = EmotionAnalysisService()
        self.face_normalization_service = FaceNormalizationService()
        self.openface_service = OpenFaceService()
        self.valence_arousal_service = ValenceArousalService()
        self.result_aggregation_service = ResultAggregationService()

    async def analyze_video(
        self,
        file: UploadFile,
        interval_ms: int = 500,
        save_normalized_frames: bool = False,
    ) -> VideoAnalysisResponse:
        """Ejecuta el pipeline completo de análisis de video sobre *file*.

        Parameters
        ----------
        file:
            Archivo de video subido por el usuario.
        interval_ms:
            Intervalo entre frames extraídos, en milisegundos.

        Errors
        ------
        HTTPException 504:
            Si el procesamiento batch de OpenFace excede el tiempo límite.
        HTTPException 502:
            Si FeatureExtraction.exe falla con un código de salida distinto de cero.
        HTTPException 422:
            Si ningún frame sobrevive al join de AU (no se detectaron rostros).
        HTTPException 400:
            Si el archivo subido no tiene nombre.
        """
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El nombre del archivo es obligatorio.",
            )

        t_start_total = time.perf_counter()
        logger.info("=== Iniciando análisis de video: %s (intervalo=%s ms) ===", file.filename, interval_ms)

        # 1. Guardar el video como archivo temporal.
        temp_video = await self.temp_file_service.create_upload_copy(file)

        try:
            # 2. Extraer frames.
            t0 = time.perf_counter()
            frames = self.frame_extraction_service.extract(
                video_path=temp_video.path,
                interval_ms=interval_ms,
            )
            duration_ms = frames[0].duration_ms
            t_extract = time.perf_counter() - t0
            logger.info("[1/4] Extracción de frames: %d frames en %.1fs", len(frames), t_extract)

            # El mismo recorte con margen se utiliza para OpenFace y el predictor.
            preview_dir = None
            if save_normalized_frames:
                file_stem = re.sub(r"[^A-Za-z0-9_-]+", "_", Path(file.filename).stem) or "video"
                run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
                preview_dir = Path(settings.recording_output_path) / "normalized_frames" / f"{file_stem}_{run_id}"
            normalized_count = 0
            if settings.face_normalization_enabled:
                normalized_count = self.face_normalization_service.normalize_files(
                    [frame.path for frame in frames], preview_dir=preview_dir
                )
            elif preview_dir is not None:
                self.face_normalization_service.save_files(
                    [frame.path for frame in frames], preview_dir
                )

            # 3. Determinar el directorio compartido desde el primer frame.
            frames_dir: Path = frames[0].path.parent

            # 4. Ejecutar OpenFace batch una sola vez.
            t0 = time.perf_counter()
            logger.info("[2/4] Iniciando OpenFace batch sobre %d frames...", len(frames))
            try:
                au_index: dict[int, dict[str, float]] = (
                    self.openface_service.analyze_frame_directory(frames_dir)
                )
                t_openface = time.perf_counter() - t0
                logger.info("[2/4] OpenFace batch completado: %d frames con AU en %.1fs",
                            len(au_index), t_openface)
            except RuntimeError as exc:
                self.frame_extraction_service.cleanup(frames)
                self._map_openface_error(exc)

            # 5. Procesar solo los frames que sobrevivieron al join de AU.
            t0 = time.perf_counter()
            skipped_faces = 0
            skipped_emotion_faces = 0
            frame_results: list[FrameResult] = []
            for capture in frames:
                au_values = au_index.get(capture.index)
                if au_values is None:
                    skipped_faces += 1
                    continue

                try:
                    emotion_result = self.emotion_service.analyze_image(capture.path)
                except ValueError as exc:
                    # OpenFace y el predictor emocional tienen detectores faciales
                    # independientes: OpenFace puede producir AU aunque el
                    # predictor no encuentre un rostro usable en ese frame.
                    if self._is_missing_face_error(exc):
                        skipped_emotion_faces += 1
                        continue
                    raise
                affect_result = self.valence_arousal_service.compute(
                    emotion_probabilities=emotion_result["emotion_probabilities"],  # type: ignore[arg-type]
                    action_units=au_values,
                )
                analysis = self.result_aggregation_service.consolidate_image(
                    emotion_result=emotion_result,
                    au_result=au_values,
                    affect_result=affect_result,
                )
                frame_results.append(FrameResult(
                    index=capture.index,
                    timestampMs=capture.timestamp_ms,
                    analysis=analysis,
                ))
            t_emotion = time.perf_counter() - t0
            if skipped_faces > 0:
                logger.warning("[3/4] %d frames omitidos (sin rostro detectado)", skipped_faces)
            if skipped_emotion_faces > 0:
                logger.warning(
                    "[3/4] %d frames omitidos: OpenFace tenía AU, pero el predictor emocional no detectó un rostro usable",
                    skipped_emotion_faces,
                )
            logger.info("[3/4] Análisis de emociones: %d frames procesados en %.1fs",
                        len(frame_results), t_emotion)

            # 6. Exigir al menos un frame analizable.
            if not frame_results:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        "No se detectaron rostros en ningún frame extraído. "
                        "El video podría no contener un rostro visible."
                    ),
                )

            # 7. Construir resumen agregado.
            summary = self._build_summary(frame_results)

            # 8. Limpiar el directorio de frames.
            self.frame_extraction_service.cleanup(frames)

            t_total = time.perf_counter() - t_start_total
            logger.info("[4/4] Resumen construido. Emoción dominante: %s, valencia prom: %.3f, arousal prom: %.3f",
                        summary.dominant_emotion, summary.avg_valence, summary.avg_arousal)
            logger.info("=== Análisis completado en %.1fs totales ===", t_total)

            processing_notes = [
                f"Video procesado: {len(frame_results)} frames analizados "
                f"a intervalos de {interval_ms} ms (modo batch OpenFace). Duración real: {duration_ms / 1000:.3f} s.",
                "Los frames donde no se detectó rostro se omiten de los resultados.",
                (
                    f"Se omitieron {skipped_emotion_faces} frames en los que OpenFace tenía AU "
                    "pero el predictor emocional no detectó un rostro usable."
                    if skipped_emotion_faces
                    else "No hubo frames rechazados por el detector facial del predictor emocional."
                ),
                (
                    f"Normalización facial aplicada a {normalized_count} frames con margen del 30%."
                    if settings.face_normalization_enabled
                    else "Normalización facial desactivada; se analizaron los frames originales."
                ),
            ]
            if preview_dir is not None:
                processing_notes.append(f"Frames normalizados guardados en: {preview_dir}")

            return VideoAnalysisResponse(
                frames=frame_results,
                summary=summary,
                durationMs=duration_ms,
                processing=ProcessingMetadata(
                    inputType="video",
                    framesProcessed=len(frame_results),
                    mode="real",
                    notes=processing_notes,
                ),
            )

        finally:
            self.temp_file_service.cleanup(temp_video.path)

    # ------------------------------------------------------------------
    # Métodos privados
    # ------------------------------------------------------------------

    @staticmethod
    def _is_missing_face_error(exc: ValueError) -> bool:
        message = str(exc).lower()
        return (
            "no se detectó ningún rostro" in message
            or "no se detecto ningun rostro" in message
        )

    @staticmethod
    def _map_openface_error(exc: RuntimeError) -> None:
        """Traduce RuntimeError de OpenFaceService a excepciones HTTP apropiadas.

        - "timed out" en el mensaje → 504 Gateway Timeout
        - Cualquier otro RuntimeError → 502 Bad Gateway
        """
        message = str(exc)
        if "timed out" in message.lower():
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"El procesamiento de OpenFace excedió el tiempo límite: {message}",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"El procesamiento de OpenFace falló: {message}",
        ) from exc

    @staticmethod
    def _build_summary(frame_results: list[FrameResult]) -> VideoSummary:
        """Construye un resumen agregado a partir de los resultados por frame."""
        if not frame_results:
            return VideoSummary(
                totalFrames=0,
                dominantEmotion="N/A",
                avgValence=0.0,
                avgArousal=0.0,
                valenceTimeline=[],
                arousalTimeline=[],
                dominantTimeline=[],
                russellPoints=[],
            )

        total = len(frame_results)

        valences = [fr.analysis.valence for fr in frame_results]
        arousals = [fr.analysis.arousal for fr in frame_results]
        def comparable_dominant(frame: FrameResult) -> str:
            probabilities = frame.analysis.emotion_probabilities
            comparable = {
                name: value for name, value in probabilities.items() if name != "Desprecio"
            }
            return max(comparable, key=comparable.get) if comparable else frame.analysis.dominant_emotion

        dominants = [comparable_dominant(fr) for fr in frame_results]
        points = [fr.analysis.russell_point for fr in frame_results]

        global_dominant = max(set(dominants), key=dominants.count)

        return VideoSummary(
            totalFrames=total,
            dominantEmotion=global_dominant,
            avgValence=sum(valences) / total,
            avgArousal=sum(arousals) / total,
            valenceTimeline=valences,
            arousalTimeline=arousals,
            dominantTimeline=dominants,
            russellPoints=points,
        )
