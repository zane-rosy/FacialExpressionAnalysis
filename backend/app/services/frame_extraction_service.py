import logging
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class FrameCapture:
    """Un frame extraído del video, guardado como JPEG en un directorio temporal compartido."""

    index: int
    timestamp_ms: float
    path: Path
    _shared_dir: Path | None = field(default=None, repr=False)


class FrameExtractionService:
    """Extrae frames de un video a intervalos regulares usando OpenCV.

    Todos los frames de una misma solicitud se almacenan en un solo directorio
    temporal compartido. El llamador debe invocar ``cleanup()`` para liberarlo
    al finalizar.
    """

    def extract(
        self,
        video_path: Path,
        interval_ms: int = 500,
    ) -> list[FrameCapture]:
        """Extrae frames de *video_path* a un directorio temporal compartido.

        Parameters
        ----------
        video_path:
            Ruta al archivo de video (mp4, avi, mov, mkv).
        interval_ms:
            Intervalo entre frames extraídos, en milisegundos.

        Returns
        -------
        list[FrameCapture]
            Frames extraídos, ordenados por marca de tiempo, todos en un solo
            directorio temporal.

        Raises
        ------
        ValueError
            Si el video no se puede abrir o no tiene frames legibles.
        """
        cap = cv2.VideoCapture(str(video_path))

        if not cap.isOpened():
            raise ValueError(
                f"No se pudo abrir el video: {video_path}. "
                "Verificá que el formato sea soportado (mp4, avi, mov, mkv)."
            )

        try:
            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0:
                raise ValueError(
                    "No se pudo determinar los FPS del video. "
                    "El archivo puede estar corrupto o tener un codec no soportado."
                )

            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            frame_step = max(1, int(fps * interval_ms / 1000))
            expected = min(total_frames // frame_step + 1, 999) if total_frames > 0 else "?"

            logger.info("  → Video: %.1f FPS, %d frames totales, paso=%d, ~%s frames esperados",
                        fps, total_frames, frame_step, expected)

            # Un solo directorio temporal por extracción — necesario para compatibilidad con -fdir.
            shared_dir = Path(tempfile.mkdtemp())

            frames: list[FrameCapture] = []
            frame_idx = 0
            extracted = 0
            t0 = time.perf_counter()

            while True:
                ret, mat = cap.read()
                if not ret:
                    break  # fin del video

                if frame_idx % frame_step == 0:
                    timestamp_ms = (frame_idx / fps) * 1000
                    frame_path = self._save_frame(mat, extracted, shared_dir)

                    frames.append(FrameCapture(
                        index=extracted,
                        timestamp_ms=round(timestamp_ms, 1),
                        path=frame_path,
                        _shared_dir=shared_dir,
                    ))
                    extracted += 1

                frame_idx += 1

            if not frames:
                # Limpiar el directorio vacío antes de lanzar la excepción.
                shutil.rmtree(shared_dir, ignore_errors=True)
                raise ValueError(
                    "No se pudo extraer ningún frame del video. "
                    "El archivo puede estar vacío o tener un formato no soportado."
                )

            t_extract = time.perf_counter() - t0
            logger.info("  → %d frames extraídos en %.1fs (directorio: %s)",
                        len(frames), t_extract, shared_dir)
            return frames

        finally:
            cap.release()

    # ------------------------------------------------------------------
    # Privado
    # ------------------------------------------------------------------

    @staticmethod
    def _save_frame(mat: np.ndarray, index: int, shared_dir: Path) -> Path:
        """Guarda *mat* como JPEG en *shared_dir* y retorna la ruta."""
        frame_path = shared_dir / f"_frame{index:04d}.jpg"
        success = cv2.imwrite(str(frame_path), mat)
        if not success:
            raise RuntimeError(f"No se pudo escribir el frame temporal: {frame_path}")
        return frame_path

    @staticmethod
    def cleanup(frames: list[FrameCapture]) -> None:
        """Elimina el directorio temporal compartido de *frames*."""
        if not frames:
            return
        shared_dir = frames[0]._shared_dir
        if shared_dir is not None:
            shutil.rmtree(shared_dir, ignore_errors=True)
