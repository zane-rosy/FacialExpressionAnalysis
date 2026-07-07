/**
 * Puntos de referencia para las 28 emociones del modelo circumplejo de Russell.
 *
 * Coordenadas normalizadas: x = valencia, y = arousal, ambas en [-1, 1].
 * El radio indica la prototipicidad/intensidad de la emoción:
 *   - outer  (1.0): emoción muy prototípica, cerca del borde del plano.
 *   - middle (0.7): emoción de intensidad media.
 *   - inner  (0.4): emoción más ambigua o menos intensa, cerca del centro.
 */

export interface RussellEmotion {
  label: string;
  x: number;
  y: number;
  ring: 'outer' | 'middle' | 'inner';
}

export const RUSSELL_EMOTIONS: RussellEmotion[] = [
  // ── Alta activación / valencia neutra-positiva ──
  { label: 'Asombrado',   x:  0.08, y:  0.92, ring: 'outer'  },  // Astonished
  { label: 'Excitado',    x:  0.50, y:  0.84, ring: 'outer'  },  // Excited
  { label: 'Alarmado',    x: -0.28, y:  0.88, ring: 'outer'  },  // Alarmed

  // ── Alta activación / valencia negativa ──
  { label: 'Asustado',    x: -0.52, y:  0.78, ring: 'outer'  },  // Afraid
  { label: 'Tenso',       x: -0.38, y:  0.78, ring: 'outer'  },  // Tense
  { label: 'Enojado',     x: -0.60, y:  0.70, ring: 'outer'  },  // Angry
  { label: 'Molesto',     x: -0.68, y:  0.60, ring: 'outer'  },  // Annoyed
  { label: 'Frustrado',   x: -0.82, y:  0.52, ring: 'outer'  },  // Frustrated
  { label: 'Angustiado',  x: -0.78, y:  0.45, ring: 'outer'  },  // Distressed

  // ── Alta activación / valencia positiva ──
  { label: 'Activado',    x:  0.20, y:  0.72, ring: 'middle' },  // Aroused
  { label: 'Feliz',       x:  0.68, y:  0.68, ring: 'outer'  },  // Happy
  { label: 'Encantado',   x:  0.65, y:  0.52, ring: 'middle' },  // Delighted
  { label: 'Alegre',      x:  0.80, y:  0.32, ring: 'outer'  },  // Glad

  // ── Valencia positiva / baja activación ──
  { label: 'Complacido',  x:  0.85, y:  0.12, ring: 'outer'  },  // Pleased
  { label: 'Contento',    x:  0.78, y: -0.12, ring: 'middle' },  // Content
  { label: 'Satisfecho',  x:  0.88, y: -0.28, ring: 'outer'  },  // Satisfied
  { label: 'A gusto',     x:  0.62, y: -0.40, ring: 'middle' },  // At ease
  { label: 'Sereno',      x:  0.42, y: -0.40, ring: 'inner'  },  // Serene
  { label: 'Calmado',     x:  0.50, y: -0.55, ring: 'middle' },  // Calm
  { label: 'Relajado',    x:  0.70, y: -0.71, ring: 'outer'  },  // Relaxed

  // ── Baja activación / valencia neutra-positiva ──
  { label: 'Somnoliento', x:  0.48, y: -0.82, ring: 'outer'  },  // Sleepy
  { label: 'Cansado',     x:  0.18, y: -0.88, ring: 'outer'  },  // Tired
  { label: 'Abatido',     x: -0.08, y: -0.90, ring: 'outer'  },  // Droopy

  // ── Baja activación / valencia negativa ──
  { label: 'Aburrido',    x: -0.35, y: -0.78, ring: 'outer'  },  // Bored
  { label: 'Melancólico', x: -0.52, y: -0.60, ring: 'middle' },  // Gloomy
  { label: 'Deprimido',   x: -0.65, y: -0.40, ring: 'middle' },  // Depressed
  { label: 'Triste',      x: -0.62, y: -0.22, ring: 'middle' },  // Sad
  { label: 'Apenado',     x: -0.80, y: -0.08, ring: 'middle' },  // Miserable
];
