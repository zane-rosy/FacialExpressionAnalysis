"""Single source of truth for the Paltoglou/Thelwall affective states."""

from math import hypot

from app.data.affective_state_catalog import AffectiveState, AFFECTIVE_STATES


class AffectiveStateService:
    def get_states(self) -> list[AffectiveState]:
        return list(AFFECTIVE_STATES)

    def get_nearest_state(self, valence: float, arousal: float) -> dict[str, float | str]:
        state = min(self.get_states(), key=lambda item: hypot(valence - item.valence, arousal - item.arousal))
        return {
            "name": state.name,
            "valence": state.valence,
            "arousal": state.arousal,
            "distance": hypot(valence - state.valence, arousal - state.arousal),
        }
