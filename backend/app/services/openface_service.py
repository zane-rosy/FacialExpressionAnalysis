import subprocess
from pathlib import Path

from app.core.config import settings
from app.parsers.openface_csv_parser import OpenFaceCsvParser

_OPENFACE_TIMEOUT_SECONDS = 30


class OpenFaceService:
    """Ejecuta OpenFace FaceLandmarkImg y retorna los valores de intensidad de AU.

    El servicio ejecuta OpenFace como subproceso, localiza el CSV que escribe,
    delega el análisis a :class:`OpenFaceCsvParser` y limpia los archivos temporales.
    """

    def __init__(self) -> None:
        self._parser = OpenFaceCsvParser()
        self._executable = Path(settings.openface_executable_path)
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
            Mapeo de nombre de AU (ej. ``AU01_r``) a valor de intensidad.

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

    # ------------------------------------------------------------------
    # Métodos privados
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
            pass  # Limpieza de mejor esfuerzo; no enmascarar la excepción de quien llama.
