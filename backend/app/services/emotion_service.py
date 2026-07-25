import sys
from decimal import Decimal
from pathlib import Path

from app.core.config import settings


class EmotionAnalysisService:
    """Analiza la emoción facial delegando en API_Emotion_Recognition.
    """

    def __init__(self) -> None:
        module_path = str(settings.emotion_module_path)
        if module_path not in sys.path:
            sys.path.insert(0, module_path)

        import Functions  # noqa: PLC0415
        self._Functions = Functions

    def analyze_image(self, image_path: Path) -> dict[str, object]:
        """Ejecuta la función de API_Emotion_Recognition

        Returns
        -------
        dict con ``dominant_emotion`` (str) y ``emotion_probabilities`` (dict[str, Decimal]).
        """
        try:
            result = self._Functions.analizar_emocion(str(image_path))
        except Exception as exc:
            raise ValueError(str(exc)) from exc

        return {
            "dominant_emotion": result["dominant_emotion"],
            "emotion_probabilities": {
                k: Decimal(str(v)) for k, v in result["emotion_probabilities"].items()
            },
        }
