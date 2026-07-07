from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Raíz del repositorio: backend/app/core/config.py -> backend/app/core -> backend/app -> backend -> Tesis/
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _default_deps_dir() -> Path:
    """Retorna el directorio de dependencias por defecto dentro del repositorio.

    Se puede sobrescribir con la variable de entorno ``TESIS_DEPS_DIR``
    o una entrada en ``.env``.
    """
    env_override = Path.cwd() / "deps"
    return env_override if env_override.exists() else _REPO_ROOT / "deps"


def _default_openface_executable() -> str:
    return str(_default_deps_dir() / "OpenFace" / "FaceLandmarkImg.exe")


def _default_openface_workdir() -> str:
    return str(_default_deps_dir() / "OpenFace")


def _default_emotion_module() -> str:
    return str(_default_deps_dir() / "API_Emotion_Recognition")


def _default_shape_predictor() -> str:
    return str(_default_deps_dir() / "API_Emotion_Recognition" / "shape_predictor_68_face_landmarks.dat")


def _default_emotion_parameters() -> str:
    return str(_default_deps_dir() / "API_Emotion_Recognition" / "mat_parametros_RaFD_CK_1616.csv")


class Settings(BaseSettings):
    app_name: str = "Tesis Backend"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:4200"])

    # ---- Rutas de dependencias (todas sobrescribibles vía .env / entorno) ----

    openface_executable_path: str = Field(default_factory=_default_openface_executable)
    openface_working_directory: str = Field(default_factory=_default_openface_workdir)
    emotion_module_path: str = Field(default_factory=_default_emotion_module)
    emotion_shape_predictor_path: str = Field(default_factory=_default_shape_predictor)
    emotion_parameters_path: str = Field(default_factory=_default_emotion_parameters)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
