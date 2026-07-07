from pathlib import Path

import pandas as pd


class OpenFaceCsvParser:
    """Analiza el CSV generado por OpenFace FaceLandmarkImg.

    OpenFace escribe una fila de encabezado seguida de una fila de datos por imagen procesada.
    Solo se extraen las columnas cuyos nombres terminan en ``_r`` (valores de intensidad de AU).
    """

    def parse(self, csv_path: Path) -> dict[str, float]:
        """Lee *csv_path* y retorna un mapeo de nombre de AU a valor de intensidad.

        Parameters
        ----------
        csv_path:
            Ruta absoluta al archivo CSV escrito por OpenFace.

        Returns
        -------
        dict[str, float]
            Las claves son nombres de AU formateados (ej. ``AU 01``).
            Los valores son las intensidades flotantes de la primera fila de datos.

        Raises
        ------
        FileNotFoundError
            Si *csv_path* no existe.
        ValueError
            Si el CSV no contiene columnas ``_r`` o no se puede analizar.
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

        # Limpiar espacios al inicio/final de los nombres de columna (OpenFace agrega
        # un espacio inicial antes de la mayoría de los nombres).
        df.columns = [col.strip() for col in df.columns]

        au_columns = [col for col in df.columns if col.endswith("_r")]

        if not au_columns:
            raise ValueError(
                f"No se encontraron columnas de intensidad de AU (que terminen en '_r') en {csv_path}. "
                f"Columnas disponibles: {list(df.columns)}"
            )

        first_row = df.iloc[0]
        result = {}
        for col in au_columns:
            # Formatear nombre de AU: AU01_r -> AU 01
            au_number = col.replace("AU", "").replace("_r", "")
            formatted_name = f"AU {au_number}"
            result[formatted_name] = float(first_row[col])
        return result
