from app.data.affective_state_catalog import AFFECTIVE_STATES
from app.services.dimensional_affect_service import DimensionalAffectService
from decimal import Decimal


def test_reference_lexicon_has_34_states():
    assert len(AFFECTIVE_STATES) == 34
    assert len({state.name for state in AFFECTIVE_STATES}) == 34


def test_nearest_state_and_top_three_are_distance_ranked():
    result = DimensionalAffectService().classify(0.70, 0.71)
    assert result["label"] == "Excited"
    matches = result["topMatches"]
    assert len(matches) == 3
    assert [match["distance"] for match in matches] == sorted(match["distance"] for match in matches)
    assert "probability" not in str(result).lower()


def test_exact_match_gets_all_proximity_weight():
    result = DimensionalAffectService().classify(0.70, 0.71)
    assert result["proximityWeight"] == 1.0
    assert result["topMatches"][1]["proximityWeight"] == 0.0


def test_decimal_inputs_are_supported():
    result = DimensionalAffectService().classify(Decimal("0.70"), Decimal("0.71"))
    assert result["label"] == "Excited"


def test_positive_valence_does_not_include_negative_valence_worried_state():
    result = DimensionalAffectService().classify(0.3333, -0.1819)
    labels = [match["label"] for match in result["topMatches"]]

    assert result["label"] == "Impressed"
    assert "Worried" not in labels
    assert all(match["valence"] >= 0 for match in result["topMatches"])
