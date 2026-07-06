import sys
from decimal import Decimal
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from app.core.config import settings

# Etiquetas de emociones indexadas por la posición de salida del clasificador (0-7).
_EMOTION_LABELS = [
    "Enojo",      # 0
    "Desprecio",  # 1
    "Asco",       # 2
    "Miedo",      # 3
    "Felicidad",  # 4
    "Neutral",    # 5
    "Tristeza",   # 6
    "Sorpresa",   # 7
]


class EmotionAnalysisService:
    """Analiza la emoción facial usando el modelo API_Emotion_Recognition.

    Agrega el directorio del módulo heredado a ``sys.path`` una vez y carga
    la matriz de parámetros de regresión logística en el constructor para que
    la operación de E/S costosa ocurra una sola vez durante la vida útil de la aplicación.
    """

    def __init__(self) -> None:
        # Asegurar que el módulo heredado sea importable.
        module_path = str(settings.emotion_module_path)
        if module_path not in sys.path:
            sys.path.insert(0, module_path)

        # Cargar la matriz de parámetros una sola vez.
        parameters_path = Path(settings.emotion_parameters_path)
        try:
            df_theta = pd.read_csv(
                parameters_path,
                delimiter=";",
                header=None,
                dtype=np.float64,
                decimal=",",
                float_precision="high",
            )
            self._theta: np.ndarray = np.asarray(df_theta)
        except Exception as exc:
            raise ValueError(
                f"No se pudo cargar la matriz de parámetros de emociones desde "
                f"{parameters_path}: {exc}"
            ) from exc

    def analyze_image(self, image_path: Path) -> dict[str, object]:
        """Ejecuta el pipeline completo de reconocimiento de emociones sobre *image_path*.

        Parameters
        ----------
        image_path:
            Ruta al archivo de imagen a analizar.

        Returns
        -------
        dict con las claves:
            - ``dominant_emotion`` (str): etiqueta del clasificador con mayor probabilidad.
            - ``emotion_probabilities`` (dict[str, float]): probabilidad por
              emoción (cada probabilidad es un clasificador independiente).

        Raises
        ------
        ValueError
            Ante cualquier fallo en el pipeline (archivo no encontrado, rostro no detectado, etc.).
        """
        import dlib  # Importar después de parchear sys.path.
        import Functions  # noqa: PLC0415  # Módulo heredado — debe importarse en tiempo de ejecución.

        # --- Paso 1: cargar imagen con OpenCV ---
        try:
            image = cv2.imread(str(image_path))
        except Exception as exc:
            raise ValueError(
                f"cv2.imread falló para {image_path}: {exc}"
            ) from exc

        if image is None:
            raise ValueError(
                f"cv2.imread retornó None para {image_path}. "
                "El archivo puede faltar, estar corrupto o tener un formato no soportado."
            )

        # --- Paso 2: convertir a escala de grises ---
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # --- Paso 3: detectar rostro frontal ---
        try:
            detector = dlib.get_frontal_face_detector()
        except Exception as exc:
            raise ValueError(
                f"No se pudo inicializar el detector de rostros dlib: {exc}"
            ) from exc

        faces = detector(gray)
        if len(faces) == 0:
            raise ValueError(
                "No se detectó ningún rostro en la imagen proporcionada. "
                "Asegurate de que la imagen contenga un rostro frontal claramente visible."
            )

        # Usar solo el primer rostro detectado (coincide con el comportamiento heredado).
        face = faces[0]

        # --- Paso 4: extraer 68 landmarks ---
        shape_predictor_path = Path(settings.emotion_shape_predictor_path)
        try:
            shape_predictor = dlib.shape_predictor(str(shape_predictor_path))
        except Exception as exc:
            raise ValueError(
                f"No se pudo cargar el shape predictor de dlib desde "
                f"{shape_predictor_path}: {exc}"
            ) from exc

        landmarks = shape_predictor(gray, face)

        # Construir la matriz de características (1, 136): coordenadas x e y de los 68 landmarks.
        features = np.zeros((1, 136), dtype=np.float64)
        j = 0
        for i in range(68):
            features[0, j] = int(landmarks.part(i).x)
            j += 1
            features[0, j] = int(landmarks.part(i).y)
            j += 1

        # --- Paso 5: ejecutar clasificadores de regresión logística ---
        try:
            # Retorna un ndarray de forma (8, 1): una probabilidad por emoción.
            h = Functions.hipotesisRL(features, self._theta)
        except Exception as exc:
            raise ValueError(
                f"La computación de hipotesisRL falló: {exc}"
            ) from exc

        if h is None:
            raise ValueError("hipotesisRL retornó None inesperadamente.")

        # --- Paso 6: mapear probabilidades a etiquetas de emociones ---
        # h tiene forma (8, 1); aplanar a un arreglo 1-D de longitud 8.
        scores: np.ndarray = h[:, 0]

        emotion_probabilities: dict[str, Decimal] = {
            label: Decimal(str(scores[idx]))
            for idx, label in enumerate(_EMOTION_LABELS)
        }

        # La emoción dominante es la que tiene la probabilidad más alta.
        dominant_index = int(np.argmax(scores))
        dominant_emotion = _EMOTION_LABELS[dominant_index]

        return {
            "dominant_emotion": dominant_emotion,
            "emotion_probabilities": emotion_probabilities,
        }
