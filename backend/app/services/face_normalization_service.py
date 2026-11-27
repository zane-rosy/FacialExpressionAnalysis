"""Preprocesamiento facial común para OpenFace y el predictor emocional."""

import logging
import shutil
from pathlib import Path

import cv2

logger = logging.getLogger(__name__)


class FaceNormalizationService:
    """Recorta el rostro principal conservando un margen contextual.

    El recorte se escribe sobre el frame temporal que luego consumen tanto
    OpenFace como el predictor emocional. Si no se detecta un rostro, se
    conserva el frame original para no descartar silenciosamente la muestra.
    """

    def __init__(self, margin_ratio: float = 0.30) -> None:
        self.margin_ratio = margin_ratio
        cascade_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
        self._detector = cv2.CascadeClassifier(str(cascade_path))
        if self._detector.empty():
            raise RuntimeError(f"No se pudo cargar el detector facial: {cascade_path}")

    def normalize_file(self, image_path: Path) -> bool:
        """Recorta y guarda el rostro principal en *image_path*.

        Retorna ``True`` si se aplicó el recorte y ``False`` si se conserva la
        imagen original porque no se detectó un rostro.
        """
        image = cv2.imread(str(image_path))
        if image is None:
            raise ValueError(f"No se pudo leer la imagen para normalizar: {image_path}")

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = self._detector.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(40, 40),
        )
        if len(faces) == 0:
            logger.warning("No se detectó rostro en %s; se conserva el frame completo", image_path.name)
            return False

        x, y, width, height = max(faces, key=lambda face: int(face[2]) * int(face[3]))
        margin_x = int(width * self.margin_ratio)
        margin_y = int(height * self.margin_ratio)
        left = max(0, x - margin_x)
        top = max(0, y - margin_y)
        right = min(image.shape[1], x + width + margin_x)
        bottom = min(image.shape[0], y + height + margin_y)
        crop = image[top:bottom, left:right]

        if crop.size == 0 or not cv2.imwrite(str(image_path), crop):
            raise RuntimeError(f"No se pudo guardar el rostro normalizado: {image_path}")
        return True

    def normalize_files(self, image_paths: list[Path], preview_dir: Path | None = None) -> int:
        """Normaliza una colección y retorna la cantidad de recortes aplicados.

        Cuando ``preview_dir`` se informa, conserva una copia de cada frame
        normalizado para inspección visual sin alterar el pipeline temporal.
        """
        if preview_dir is not None:
            preview_dir.mkdir(parents=True, exist_ok=True)
        normalized = 0
        for path in image_paths:
            normalized += int(self.normalize_file(path))
            if preview_dir is not None:
                shutil.copy2(path, preview_dir / path.name)
        logger.info("Normalización facial: %d/%d frames recortados con margen %.0f%%",
                    normalized, len(image_paths), self.margin_ratio * 100)
        return normalized

    @staticmethod
    def save_files(image_paths: list[Path], preview_dir: Path) -> None:
        """Conserva frames sin normalizar para una ejecución de comparación."""
        preview_dir.mkdir(parents=True, exist_ok=True)
        for path in image_paths:
            shutil.copy2(path, preview_dir / path.name)
