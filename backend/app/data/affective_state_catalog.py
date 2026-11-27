"""Reference affective states used by the dimensional interpretation.

Coordinates are expressed in the same normalized [-1, 1] valence/arousal
space used by the application.  They are kept as data, rather than inferred
from the categorical classifier, so the two interpretations remain separate.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AffectiveState:
    name: str
    valence: float
    arousal: float


# Paltoglou & Thelwall reference lexicon (34 states). The order and values
# below are the rows transcribed from Table 1; x is valence and y is arousal.
AFFECTIVE_STATES: tuple[AffectiveState, ...] = (
    AffectiveState("Sleepy", 0.01, -1.00), AffectiveState("Tired", -0.01, -1.00),
    AffectiveState("Afraid", -0.12, 0.79), AffectiveState("Angry", -0.40, 0.79),
    AffectiveState("Calm", 0.78, -0.68), AffectiveState("Relaxed", 0.71, -0.65),
    AffectiveState("Content", 0.81, -0.55), AffectiveState("Depressed", -0.81, -0.48),
    AffectiveState("Discontent", -0.68, -0.32), AffectiveState("Determined", 0.73, 0.26),
    AffectiveState("Happy", 0.89, 0.17), AffectiveState("Anxious", -0.72, -0.80),
    AffectiveState("Good", 0.90, -0.08), AffectiveState("Pensive", 0.03, -0.60),
    AffectiveState("Impressed", 0.39, -0.06), AffectiveState("Frustrated", -0.60, 0.40),
    AffectiveState("Disappointed", -0.80, -0.03), AffectiveState("Bored", -0.35, -0.78),
    AffectiveState("Annoyed", -0.44, 0.76), AffectiveState("Enraged", -0.18, 0.83),
    AffectiveState("Excited", 0.70, 0.71), AffectiveState("Melancholy", -0.05, -0.65),
    AffectiveState("Satisfied", 0.77, -0.63), AffectiveState("Distressed", -0.71, 0.55),
    AffectiveState("Uncomfortable", -0.68, -0.37), AffectiveState("Worried", -0.07, -0.32),
    AffectiveState("Amused", 0.55, 0.19), AffectiveState("Apathetic", -0.20, -0.12),
    AffectiveState("Peaceful", 0.55, -0.80), AffectiveState("Contemplative", 0.58, -0.60),
    AffectiveState("Embarrassed", -0.31, -0.60), AffectiveState("Sad", -0.81, -0.40),
    AffectiveState("Hopeful", 0.61, -0.30), AffectiveState("Pleased", 0.89, -0.10),
)

assert len(AFFECTIVE_STATES) == 34
