import logging
import subprocess
import tempfile
import time
from pathlib import Path

from app.core.config import settings
from app.parsers.openface_csv_parser import OpenFaceCsvParser, parse_video_csv

logger = logging.getLogger(__name__)

# Timeout para análisis de imagen individual (FaceLandmarkImg.exe). Se mantiene corto
# intencionalmente: el procesamiento por imagen debería completarse en segundos; usar
# settings.openface_batch_timeout_seconds para la llamada batch a FeatureExtraction.exe
# que procesa muchos frames de una sola vez.
_OPENFACE_TIMEOUT_SECONDS = 30


class OpenFaceService:
    """Ejecuta OpenFace y retorna los valores de intensidad de AU.

    Soporta análisis de imagen individual con FaceLandmarkImg.exe y análisis
    de directorio de frames con FeatureExtraction.exe -fdir.
    """

    def __init__(self) -> None:
        self._parser = OpenFaceCsvParser()
        self._executable = Path(settings.openface_executable_path)
        self._feature_extraction_exe = Path(settings.openface_feature_extraction_path)
        self._working_dir = Path(settings.openface_working_directory)

    def analyze_image(self, image_path: Path) -> dict[str, float]:
        """Ejecuta OpenFace sobre *image_path* y retorna los valores de intensidad de AU.

        Parameters
        ----------
        image_path:
            Ruta absoluta al archivo de imagen.

        Returns
        -------
        dict[str, float]
            Mapeo de nombre de AU (ej. ``AU 01``) a valor de intensidad.

        Raises
        ------
        RuntimeError
            Si el proceso de OpenFace termina con código no cero, expira, o
            no se encuentra el CSV de salida.
        """
        command = [str(self._executable), "-f", str(image_path), "-aus"]

        try:
            result = subprocess.run(
                command,
                cwd=str(self._working_dir),
                capture_output=True,
                text=True,
                timeout=_OPENFACE_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"OpenFace expiró después de {_OPENFACE_TIMEOUT_SECONDS}s "
                f"procesando {image_path}"
            ) from exc
        except Exception as exc:
            raise RuntimeError(
                f"No se pudo lanzar el ejecutable de OpenFace en {self._executable}: {exc}"
            ) from exc

        if result.returncode != 0:
            raise RuntimeError(
                f"OpenFace terminó con código {result.returncode}.\n"
                f"stderr: {result.stderr}\nstdout: {result.stdout}"
            )

        # Localizar el CSV que escribió OpenFace.
        csv_path = self._find_output_csv(image_path)

        try:
            au_values = self._parser.parse(csv_path)
        finally:
            # Siempre limpiar el CSV, incluso si el análisis falla.
            self._cleanup_csv(csv_path)

        return au_values

    def analyze_frame_directory(self, frame_dir: Path) -> dict[int, dict[str, float]]:
        """Ejecuta FeatureExtraction.exe sobre *frame_dir* y retorna un mapa frame-índice → AU.

        Invoca ``FeatureExtraction.exe -fdir <dir> -aus -of <csv_path>`` una sola vez.
        Analiza el CSV resultante con :func:`parse_video_csv`, mapea los números de frame
        1-based de OpenFace a índices 0-based de la API, y retorna solo las filas donde
        hay datos de AU disponibles.

        Parameters
        ----------
        frame_dir:
            Directorio que contiene los frames JPEG nombrados ``_frame0000.jpg`` …

        Returns
        -------
        dict[int, dict[str, float]]
            Mapeo de índice de frame 0-based → nombre de AU → valor de intensidad.

        Errors
        ------
        RuntimeError
            Por timeout, código de salida no cero, CSV de salida no encontrado, o error de análisis.
        """
        timeout = settings.openface_batch_timeout_seconds
        logger.info("    → Ejecutando FeatureExtraction.exe -fdir %s (timeout=%ds)...",
                    frame_dir, timeout)

        # Usar una ruta de salida CSV determinística en un archivo temporal
        # para saber siempre dónde encontrar el resultado.
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp_f:
            csv_path = Path(tmp_f.name)

        command = [
            str(self._feature_extraction_exe),
            "-fdir", str(frame_dir),
            "-aus",
            "-of", str(csv_path),
        ]

        t0 = time.perf_counter()
        try:
            result = subprocess.run(
                command,
                cwd=str(self._working_dir),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            self._cleanup_csv(csv_path)
            raise RuntimeError(
                f"El procesamiento batch de OpenFace excedió el tiempo límite de {timeout}s "
                f"para el directorio {frame_dir}"
            ) from exc
        except Exception as exc:
            self._cleanup_csv(csv_path)
            raise RuntimeError(
                f"No se pudo lanzar FeatureExtraction.exe en {self._feature_extraction_exe}: {exc}"
            ) from exc

        t_exe = time.perf_counter() - t0
        logger.info("    → FeatureExtraction.exe finalizó en %.1fs (código=%d)", t_exe, result.returncode)

        if result.returncode != 0:
            self._cleanup_csv(csv_path)
            raise RuntimeError(
                f"FeatureExtraction.exe terminó con código {result.returncode}.\n"
                f"stderr: {result.stderr}\nstdout: {result.stdout}"
            )

        if not csv_path.exists():
            raise RuntimeError(
                f"FeatureExtraction.exe finalizó pero no se escribió el CSV de salida: {csv_path}"
            )

        try:
            rows = parse_video_csv(csv_path)
        except Exception as exc:
            raise RuntimeError(
                f"No se pudo analizar el CSV de salida de OpenFace en {csv_path}: {exc}"
            ) from exc
        finally:
            self._cleanup_csv(csv_path)

        au_index = {
            row.frame_number - 1: row.action_units
            for row in rows
            if row.action_units
        }
        logger.info("    → CSV analizado: %d filas con AU de %d filas totales",
                    len(au_index), len(rows))

        # Convertir números de frame 1-based de OpenFace a índices 0-based de la API.
        return au_index

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _find_output_csv(self, image_path: Path) -> Path:
        """Busca el CSV que OpenFace escribió para *image_path*.

        OpenFace puede escribir en:
        1. ``<directorio_de_trabajo>/processed/<nombre>.csv``
        2. ``<directorio_padre_de_imagen>/<nombre>.csv``

        Retorna la primera coincidencia encontrada, o lanza :class:`RuntimeError`.
        """
        stem = image_path.stem

        candidates = [
            self._working_dir / "processed" / f"{stem}.csv",
            image_path.parent / f"{stem}.csv",
        ]

        for candidate in candidates:
            if candidate.exists():
                return candidate

        raise RuntimeError(
            f"No se encontró el CSV de salida de OpenFace para la imagen '{image_path.name}'. "
            f"Ubicaciones buscadas: {[str(c) for c in candidates]}"
        )

    @staticmethod
    def _cleanup_csv(csv_path: Path) -> None:
        """Elimina *csv_path* si existe, ignorando errores silenciosamente."""
        try:
            if csv_path.exists():
                csv_path.unlink()
        except Exception:
            pass  # Best-effort cleanup; do not mask the caller's exception.
