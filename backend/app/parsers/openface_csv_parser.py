from dataclasses import dataclass
from pathlib import Path

import pandas as pd

_DEFAULT_CONFIDENCE_THRESHOLD = 0.5

# AUs disponibles en el módulo de análisis de AUs de FaceReader.
# Se conservan con el formato normalizado que expone este parser (AU NN).
FACEREADER_ACTION_UNITS = frozenset({
    "AU 01", "AU 02", "AU 04", "AU 05", "AU 06",
    "AU 07", "AU 09", "AU 10", "AU 12", "AU 14",
    "AU 15", "AU 17", "AU 18", "AU 20", "AU 23",
    "AU 24", "AU 25", "AU 26", "AU 27", "AU 43",
})


@dataclass(frozen=True)
class ParsedVideoAuRow:
    """A single frame's AU data from an OpenFace video CSV."""

    frame_number: int
    success: bool
    action_units: dict[str, float]


def _load_dataframe(csv_path: Path) -> tuple[pd.DataFrame, list[str]]:
    """Carga un CSV de OpenFace y retorna el DataFrame más los nombres de columnas de intensidad AU.

    Parameters
        ----------
        csv_path:
            Ruta absoluta al archivo CSV escrito por OpenFace.

    Returns
        -------
        dict[str, float]
            Las claves son nombres de AU formateados (ej. ``AU 01``).
            Los valores son las intensidades de la primera fila de datos.
            
    Errors
    ------
    FileNotFoundError
        Si *csv_path* no existe.
    ValueError
        Si el archivo no se puede analizar o no contiene columnas ``_r`` de AU.
    """
    if not csv_path.exists():
        raise FileNotFoundError(
            f"No se encontró el CSV de salida de OpenFace: {csv_path}"
        )

    try:
        df = pd.read_csv(csv_path, skipinitialspace=True)
    except Exception as exc:
        raise ValueError(
            f"No se pudo leer el CSV de OpenFace en {csv_path}: {exc}"
        ) from exc

    df.columns = [col.strip() for col in df.columns]

    au_columns = [col for col in df.columns if col.endswith("_r")]

    if not au_columns:
        raise ValueError(
            f"No se encontraron columnas de intensidad de AU (que terminen en '_r') en {csv_path}. "
            f"Columnas disponibles: {list(df.columns)}"
        )

    return df, au_columns


def _au_dict_from_series(series: pd.Series, au_columns: list[str]) -> dict[str, float]:

    result: dict[str, float] = {}
    for col in au_columns:
        au_number = col.replace("AU", "").replace("_r", "").zfill(2)
        au_name = f"AU {au_number}"
        if au_name in FACEREADER_ACTION_UNITS:
            result[au_name] = float(series[col])
    return result


class OpenFaceCsvParser:
    """Analiza el CSV generado por OpenFace FaceLandmarkImg.

    OpenFace escribe una fila de encabezado seguida de una fila de datos por imagen procesada.
    Se extraen las columnas cuyos nombres terminan en ``_r`` (valores de intensidad de AU).
    """

    def parse(self, csv_path: Path) -> dict[str, float]:
        """Lee *csv_path* y retorna un mapeo de nombre de AU a valor de intensidad.
        """
        df, au_columns = _load_dataframe(csv_path)
        return _au_dict_from_series(df.iloc[0], au_columns)


def parse_video_csv(
    csv_path: Path,
    confidence_threshold: float = _DEFAULT_CONFIDENCE_THRESHOLD,
) -> list[ParsedVideoAuRow]:
    """Analiza un CSV de video de OpenFace y retorna una fila por cada frame detectado exitosamente.

    Filtros aplicados:
    - Solo filas donde ``face_id == 0`` (rostro principal).
    - Solo filas donde ``success == 1`` (rostro detectado).
    - Solo filas donde ``confidence >= confidence_threshold``.

    Parameters
    ----------
    csv_path:
        Ruta al CSV escrito por ``FeatureExtraction.exe``.
    confidence_threshold:
        Valor mínimo de confianza para incluir una fila. Por defecto 0.5.

    Returns
    -------
    list[ParsedVideoAuRow]
        Una entrada por cada frame aceptado, ordenado por el valor de la columna ``frame``.

    Errors
    ------
    FileNotFoundError
        Si *csv_path* no existe.
    ValueError
        Si el CSV no se puede analizar o no tiene columnas de intensidad AU.
    """
    df, au_columns = _load_dataframe(csv_path)

    # Aplicar filtros: solo rostro principal, detección exitosa, confianza suficiente.
    mask = (
        (df["face_id"] == 0)
        & (df["success"] == 1)
        & (df["confidence"] >= confidence_threshold)
    )
    filtered = df[mask].copy()

    rows: list[ParsedVideoAuRow] = []
    for _, series in filtered.iterrows():
        rows.append(ParsedVideoAuRow(
            frame_number=int(series["frame"]),
            success=bool(series["success"]),
            action_units=_au_dict_from_series(series, au_columns),
        ))

    return rows
