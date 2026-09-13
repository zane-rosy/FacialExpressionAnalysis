import logging
import time
from collections import Counter
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.schemas.analysis import (
    AnalysisResponse,
    FrameResult,
    ProcessingMetadata,
    VideoAnalysisResponse,
    VideoSummary,
)
from app.services.emotion_service import EmotionAnalysisService
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
    5. Los frames sin datos de AU (rostro no detectado) se omiten de los resultados.
    6. Construir resumen a partir de los frames supervivientes y retornar VideoAnalysisResponse.
    """

    def __init__(self) -> None:
        self.temp_file_service = TemporaryFileService()
        self.frame_extraction_service = FrameExtractionService()
        self.emotion_service = EmotionAnalysisService()
        self.openface_service = OpenFaceService()
        self.valence_arousal_service = ValenceArousalService()
        self.result_aggregation_service = ResultAggregationService()

    async def analyze_video(
        self,
        file: UploadFile,
        interval_ms: int = 500,
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
            t_extract = time.perf_counter() - t0
            logger.info("[1/4] Extracción de frames: %d frames en %.1fs", len(frames), t_extract)

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
            frame_results: list[FrameResult] = []
            for capture in frames:
                au_values = au_index.get(capture.index)
                if au_values is None:
                    skipped_faces += 1
                    continue

                emotion_result = self.emotion_service.analyze_image(capture.path)
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

            return VideoAnalysisResponse(
                frames=frame_results,
                summary=summary,
                processing=ProcessingMetadata(
                    inputType="video",
                    framesProcessed=len(frame_results),
                    mode="real",
                    notes=[
                        f"Video procesado: {len(frame_results)} frames analizados "
                        f"a intervalos de {interval_ms} ms (modo batch OpenFace).",
                        "Los frames donde no se detectó rostro se omiten de los resultados.",
                    ],
                ),
            )

        finally:
            self.temp_file_service.cleanup(temp_video.path)

    # ------------------------------------------------------------------
    # Métodos privados
    # ------------------------------------------------------------------

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
        dominants = [fr.analysis.dominant_emotion for fr in frame_results]
        points = [fr.analysis.russell_point for fr in frame_results]

        dominant_counter = Counter(dominants)
        global_dominant = dominant_counter.most_common(1)[0][0]

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
