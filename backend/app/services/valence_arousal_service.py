class ValenceArousalService:
    """Calcula valencia y arousal a partir de probabilidades de emociones y valores de AU.

    Fórmulas
    --------
    Valencia (rango natural [-1, 1], no necesita ajuste):
        valencia = P("Felicidad") - max(P("Tristeza"), P("Enojo"), P("Miedo"), P("Desprecio"))

    Arousal (transformado a [-1, 1]):
        1. Tomar los 3 valores AU_r más altos (por magnitud) de todas las AUs devueltas por OpenFace.
        2. Normalizar cada uno: au_norm = au_valor / 5.0  (la escala de AU es [1, 5]).
        3. arousal_original = promedio(top_3_normalizados).
        4. arousal_normalized = arousal_original * 2 - 1  (transformación lineal: 0→-1, 0.5→0, 1→1).

    No se aplican los factores AAV/CAV ni una ventana temporal de 60 s. La
    excitación se calcula de forma independiente para cada conjunto de AUs
    correspondiente a un frame. La transformación a [-1, 1] se conserva
    únicamente para la representación gráfica y el punto de Russell.
    """

    def compute(
        self,
        emotion_probabilities: dict[str, float],
        action_units: dict[str, float],
    ) -> dict[str, float]:
        """Retorna ``valence`` y ``arousal`` como un diccionario con esas dos claves.

        Parameters
        ----------
        emotion_probabilities:
            Probabilidades indexadas por etiqueta de emoción en español.
        action_units:
            Valores de intensidad de AU indexados por nombre de columna (ej. ``AU01_r``).
        """
        valence = self._compute_valence(emotion_probabilities)
        arousal = self._compute_arousal(action_units)

        return {
            "valence": valence,
            "arousal": arousal,
        }

    # ------------------------------------------------------------------
    # Métodos privados
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_valence(emotion_probabilities: dict[str, float]) -> float:
        """ No se aplica normalización. El rango luego del cálculo es [-1, 1].
        """
        happiness = emotion_probabilities.get("Felicidad", 0.0)

        # Afecto negativo: tomar el peor caso como único impulsor.
        negative = max(
            emotion_probabilities.get("Tristeza", 0.0),
            emotion_probabilities.get("Enojo", 0.0),
            emotion_probabilities.get("Miedo", 0.0),
            emotion_probabilities.get("Asco", 0.0),
            #emotion_probabilities.get("Desprecio", 0.0),
        )

        valence = happiness - negative
        return valence

    @staticmethod
    def _compute_arousal(action_units: dict[str, float]) -> float:
        """Arousal derivado de las 3 intensidades de AU más altas.

        Pasos:
        1. Ordenar todas las AUs por valor descendente; tomar las 3 más altas.
        2. Normalizar cada una dividiendo por 5.0 (la escala de AU es [1, 5]).
        3. Calcular el promedio de los valores normalizados.
        4. Transformar a [-1, 1]: arousal = arousal_original * 2 - 1.

        Si hay menos de 5 AUs disponibles, se usan las que existan.
        Si no hay AUs, el arousal por defecto es -1.0 (mínima activación).
        """
        if not action_units:
            return -1.0

        # Ordenar por intensidad descendente y tomar las 3 más altas.
        sorted_values = sorted(action_units.values(), reverse=True)
        top_3 = sorted_values[:3]

        # Normalizar: la escala de intensidad de AU es [1, 5], dividir por 5.0 mapea a [0, 1].
        au_norm = [v / 5.0 for v in top_3]

        # Promedio de los 3 valores normalizados.
        arousal_raw = sum(au_norm) / len(au_norm)

        # Transformación lineal de [0, 1] a [-1, 1].
        arousal = arousal_raw * 2 - 1

        return arousal
