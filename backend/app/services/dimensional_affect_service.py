"""Nearest-neighbour interpretation in the valence/arousal space."""

from app.data.affective_state_catalog import AffectiveState
from app.services.affective_state_service import AffectiveStateService


class DimensionalAffectService:
    """Maps a point to reference states; weights are not probabilities."""

    def classify(self, valence: float, arousal: float, top_k: int = 3) -> dict[str, object]:
        states = self.affective_state_service.get_states()
        same_quadrant = [
            state for state in states
            if self._same_quadrant(valence, arousal, state)
        ]
        # Si una futura tabla no tuviera estados en un cuadrante, conservar
        # el vecino global es más seguro que devolver una clasificación vacía.
        candidates = same_quadrant or states

        ranked = sorted(
            [
                (self._distance(valence, arousal, state), state)
                for state in candidates
            ],
            key=lambda pair: pair[0],
        )
        selected = ranked[: max(1, min(top_k, len(ranked)))]
        distances = [distance for distance, _ in selected]
        weights = self._weights(distances)

        def item(index: int, pair: tuple[float, AffectiveState]) -> dict[str, object]:
            distance, state = pair
            return {
                "label": state.name,
                "valence": state.valence,
                "arousal": state.arousal,
                "distance": round(distance, 6),
                "proximityWeight": round(weights[index], 6),
            }

        nearest = item(0, selected[0])
        return {
            "label": nearest["label"],
            "distance": nearest["distance"],
            "proximityWeight": nearest["proximityWeight"],
            "topMatches": [item(index, pair) for index, pair in enumerate(selected)],
        }

    @staticmethod
    def _distance(valence: float, arousal: float, state: AffectiveState) -> float:
        # Some upstream classifiers return Decimal values while the reference
        # catalog stores normalized coordinates as floats. Normalize both
        # inputs at this numeric boundary before doing Euclidean arithmetic.
        valence_value = float(valence)
        arousal_value = float(arousal)
        return ((valence_value - state.valence) ** 2 + (arousal_value - state.arousal) ** 2) ** 0.5

    @classmethod
    def _same_quadrant(cls, valence: float, arousal: float, state: AffectiveState) -> bool:
        """Respeta el cuadrante; los ejes pueden pertenecer a cualquiera de sus lados."""
        def sign(value: float) -> int:
            return 1 if float(value) >= 0 else -1

        point_x, point_y = sign(valence), sign(arousal)
        state_x, state_y = sign(state.valence), sign(state.arousal)
        on_x_axis = float(state.valence) == 0
        on_y_axis = float(state.arousal) == 0
        return (
            (point_x == state_x or on_x_axis)
            and (point_y == state_y or on_y_axis)
        )

    @staticmethod
    def _weights(distances: list[float]) -> list[float]:
        if any(distance == 0 for distance in distances):
            return [1.0 if distance == 0 else 0.0 for distance in distances]
        inverse = [1.0 / distance for distance in distances]
        total = sum(inverse)
        return [value / total for value in inverse]
    def __init__(self) -> None:
        self.affective_state_service = AffectiveStateService()
