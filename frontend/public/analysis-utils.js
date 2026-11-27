(function (global) {
  'use strict';

  // Parámetros metodológicos del análisis de ventana móvil.
  const MOVING_WINDOW_MS = 600;
  const MOVING_STEP_MS = 100;
  const MOVING_MIN_SAMPLE_RATIO = 0.80;
  const MOVING_MIN_COVERAGE_MS = 400;

  const affectiveStates = [
    ['Sleepy', 0.01, -1], ['Tired', -0.01, -1], ['Afraid', -0.12, 0.79], ['Angry', -0.40, 0.79],
    ['Calm', 0.78, -0.68], ['Relaxed', 0.71, -0.65], ['Content', 0.81, -0.55], ['Depressed', -0.81, -0.48],
    ['Discontent', -0.68, -0.32], ['Determined', 0.73, 0.26], ['Happy', 0.89, 0.17], ['Anxious', -0.72, -0.80],
    ['Good', 0.90, -0.08], ['Pensive', 0.03, -0.60], ['Impressed', 0.39, -0.06], ['Frustrated', -0.60, 0.40],
    ['Disappointed', -0.80, -0.03], ['Bored', -0.35, -0.78], ['Annoyed', -0.44, 0.76], ['Enraged', -0.18, 0.83],
    ['Excited', 0.70, 0.71], ['Melancholy', -0.05, -0.65], ['Satisfied', 0.77, -0.63], ['Distressed', -0.71, 0.55],
    ['Uncomfortable', -0.68, -0.37], ['Worried', -0.07, -0.32], ['Amused', 0.55, 0.19], ['Apathetic', -0.20, -0.12],
    ['Peaceful', 0.55, -0.80], ['Contemplative', 0.58, -0.60], ['Embarrassed', -0.31, -0.60], ['Sad', -0.81, -0.40],
    ['Hopeful', 0.61, -0.30], ['Pleased', 0.89, -0.10]
  ];

  const n = value => typeof value === 'number' && Number.isFinite(value) ? value : null;
  const mean = (rows, key) => {
    const values = rows.map(row => n(row[key])).filter(value => value != null);
    return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;
  };
  const mode = rows => {
    const counts = new Map();
    rows.map(row => row.originalDominantEmotion === 'Desprecio' && row.dominantEmotion
      ? `Desprecio (${row.dominantEmotion})` : row.dominantEmotion)
      .filter(Boolean).forEach(label => counts.set(label, (counts.get(label) || 0) + 1));
    return [...counts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] || '—';
  };
  const sameQuadrant = (pointValence, pointArousal, stateValence, stateArousal) => {
    const sign = value => value >= 0 ? 1 : -1;
    const pointX = sign(pointValence), pointY = sign(pointArousal);
    const stateX = sign(stateValence), stateY = sign(stateArousal);
    const onXAxis = stateValence === 0, onYAxis = stateArousal === 0;
    return (pointX === stateX || onXAxis) && (pointY === stateY || onYAxis);
  };
  const dimensionalLabel = (valence, arousal) => {
    if (valence == null || arousal == null) return '—';
    const sameQuadrantStates = affectiveStates.filter(state => sameQuadrant(valence, arousal, state[1], state[2]));
    const candidates = sameQuadrantStates.length ? sameQuadrantStates : affectiveStates;
    return candidates.reduce((best, state) => {
      const distance = Math.hypot(valence - state[1], arousal - state[2]);
      return distance < best.distance ? { name: state[0], distance } : best;
    }, { name: '—', distance: Infinity }).name;
  };
  const displayAffect = value => {
    if (value == null) return '—';
    if (typeof value === 'number') return value.toFixed(3);
    if (typeof value === 'string') return value;
    try { return JSON.stringify(value); } catch { return String(value); }
  };
  const affectSummary = (rows, key) => {
    const values = rows.map(row => row[key]).filter(value => value != null);
    if (!values.length) return '—';
    if (values.every(value => typeof value === 'number')) return displayAffect(values.reduce((a, b) => a + b, 0) / values.length);
    if (values.every(value => value && typeof value === 'object' && !Array.isArray(value))) {
      const totals = {};
      values.forEach(value => Object.entries(value).forEach(([name, score]) => {
        if (typeof score === 'number') totals[name] = totals[name] || { sum: 0, count: 0 }, totals[name].sum += score, totals[name].count++;
      }));
      return Object.entries(totals).map(([name, total]) => [name, total.sum / total.count])
        .sort((a, b) => b[1] - a[1]).slice(0, 3)
        .map(([name, score]) => `${name} ${score.toFixed(3)}`).join(', ') || '—';
    }
    const counts = new Map(values.map(value => [displayAffect(value), 0]));
    values.forEach(value => counts.set(displayAffect(value), counts.get(displayAffect(value)) + 1));
    return [...counts.entries()].sort((a, b) => b[1] - a[1])[0][0];
  };
  const valid = row => Number.isFinite(row.timestampMs) && (n(row.valence) != null || n(row.arousal) != null || row.dominantEmotion != null);
  const normalizeSystem = payload => {
    const frames = Array.isArray(payload) ? payload : payload?.frames;
    if (!Array.isArray(frames)) throw new Error('El JSON no contiene un array ni un campo frames.');
    return frames.map(frame => {
      const analysis = frame.analysis || frame;
      const probabilities = analysis.emotionProbabilities || {};
      const comparable = Object.entries(probabilities).filter(([name]) => name !== 'Desprecio').sort(([, a], [, b]) => Number(b) - Number(a));
      const originalDominantEmotion = analysis.dominantEmotion ?? null;
      return {
        timestampMs: n(frame.timestampMs) ?? n(frame.videoTimeMs) ?? 0,
        dominantEmotion: originalDominantEmotion === 'Desprecio' ? comparable[0]?.[0] ?? originalDominantEmotion : originalDominantEmotion,
        originalDominantEmotion,
        valence: n(analysis.valence),
        arousal: n(analysis.arousal),
        attention: n(analysis.attention)
      };
    }).filter(valid);
  };
  const normalizeMorph = payload => {
    if (!Array.isArray(payload)) throw new Error('El JSON de MorphCast debe contener un array de resultados.');
    return payload.map(result => ({ ...result,
      timestampMs: n(result.timestampMs) ?? n(result.videoTimeMs) ?? 0,
      valence: n(result.valence), arousal: n(result.arousal),
      affects38: result.affects38 ?? result.raw?.face_arousal_valence?.affects38 ?? null,
      affects98: result.affects98 ?? result.raw?.face_arousal_valence?.affects98 ?? null
    })).filter(valid);
  };
  const duration = (...sets) => Math.max(0, ...sets.flat().map(row => n(row.timestampMs)).filter(value => value != null));
  const segments = (rows, totalDuration) => [0, 1, 2].map(index => {
    const from = totalDuration * index / 3, to = totalDuration * (index + 1) / 3;
    return { index, from, to, rows: rows.filter(row => row.timestampMs >= from && (index === 2 ? row.timestampMs <= to : row.timestampMs < to)) };
  });
  const segmentIndex = (timestampMs, totalDuration) => {
    if (!Number.isFinite(timestampMs) || !(totalDuration > 0)) return null;
    return Math.min(2, Math.floor(timestampMs / (totalDuration / 3)));
  };
  const pairsByCommonSegment = (pairs, totalDuration) => pairs.filter(item => {
    const morphSegment = segmentIndex(item.morph.timestampMs, totalDuration);
    const systemSegment = segmentIndex(item.system.timestampMs, totalDuration);
    return morphSegment != null && morphSegment === systemSegment;
  });
  const summarize = rows => ({ n: rows.length, valence: mean(rows, 'valence'), arousal: mean(rows, 'arousal'), categorical: mode(rows), dimensional: dimensionalLabel(mean(rows, 'valence'), mean(rows, 'arousal')), affects38: affectSummary(rows, 'affects38'), affects98: affectSummary(rows, 'affects98') });
  const movingWindows = (rows, windowMs = MOVING_WINDOW_MS, stepMs = MOVING_STEP_MS, durationMs = null) => {
    const timestamps = rows.map(row => n(row.timestampMs)).filter(value => value != null);
    if (!timestamps.length) return [];
    const maxTimestamp = Math.max(...timestamps);
    const analysisDuration = durationMs == null ? maxTimestamp : durationMs;
    if (!(analysisDuration > 0)) return [];
    const lastStart = Math.max(0, analysisDuration - windowMs);
    const windows = [];
    for (let start = 0; start <= lastStart + Number.EPSILON; start += stepMs) {
      const end = start + windowMs;
      const isLastWindow = start + stepMs > lastStart;
      const windowRows = rows.filter(row => row.timestampMs >= start && (isLastWindow ? row.timestampMs <= end : row.timestampMs < end));
      const firstTimestampMs = windowRows.length ? windowRows[0].timestampMs : null;
      const lastTimestampMs = windowRows.length ? windowRows[windowRows.length - 1].timestampMs : null;
      windows.push({
        startMs: start,
        endMs: end,
        firstTimestampMs,
        lastTimestampMs,
        coverageMs: firstTimestampMs != null && lastTimestampMs != null ? lastTimestampMs - firstTimestampMs : 0,
        ...summarize(windowRows),
      });
    }
    return windows;
  };
  const median = values => {
    if (!values.length) return null;
    const sorted = [...values].sort((a, b) => a - b);
    const middle = Math.floor(sorted.length / 2);
    return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
  };
  const movingWindowAnalysis = (rows, durationMs) => {
    const orderedRows = [...rows].sort((a, b) => a.timestampMs - b.timestampMs);
    const intervals = orderedRows.slice(1)
      .map((row, index) => row.timestampMs - orderedRows[index].timestampMs)
      .filter(interval => interval >= 0);
    const medianIntervalMs = median(intervals);
    const expectedSamples = medianIntervalMs && medianIntervalMs > 0 ? MOVING_WINDOW_MS / medianIntervalMs : null;
    const minSamples = expectedSamples != null ? Math.ceil(expectedSamples * MOVING_MIN_SAMPLE_RATIO) : null;
    const windows = movingWindows(orderedRows, MOVING_WINDOW_MS, MOVING_STEP_MS, durationMs);
    const eligibleWindows = minSamples == null ? [] : windows.filter(window =>
      window.n >= minSamples &&
      window.coverageMs >= MOVING_MIN_COVERAGE_MS &&
      window.arousal != null
    );
    const byExcitation = [...eligibleWindows]
      .sort((a, b) => b.arousal - a.arousal || a.startMs - b.startMs)[0] ?? null;
    const minimum = [...eligibleWindows]
      .sort((a, b) => a.arousal - b.arousal || a.startMs - b.startMs)[0] ?? null;
    return {
      windows,
      eligibleWindows,
      selected: byExcitation,
      maximum: byExcitation,
      minimum,
      medianIntervalMs,
      expectedSamples,
      minSamples
    };
  };
  const canonicalEmotion = label => ({ angry: 'angry', enojo: 'angry', disgust: 'disgust', asco: 'disgust', fear: 'fear', miedo: 'fear', happy: 'happy', felicidad: 'happy', neutral: 'neutral', sad: 'sad', tristeza: 'sad', surprise: 'surprise', sorpresa: 'surprise' })[String(label || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()] ?? null;
  const pair = (morph, system) => {
    const used = new Set();
    return morph.map(morphRow => {
      let best = -1, distance = Infinity;
      system.forEach((systemRow, index) => {
        if (used.has(index)) return;
        const candidate = Math.abs(systemRow.timestampMs - morphRow.timestampMs);
        if (candidate < distance) best = index, distance = candidate;
      });
      if (best < 0 || distance > 250) return null;
      used.add(best);
      return { morph: morphRow, system: system[best], distanceMs: distance };
    }).filter(Boolean);
  };
  global.AnalysisUtils = { affectiveStates, n, mean, mode, sameQuadrant, dimensionalLabel, displayAffect, affectSummary, normalizeSystem, normalizeMorph, duration, segments, segmentIndex, pairsByCommonSegment, summarize, movingWindows, movingWindowAnalysis, movingWindowMs: MOVING_WINDOW_MS, movingStepMs: MOVING_STEP_MS, movingMinSampleRatio: MOVING_MIN_SAMPLE_RATIO, movingMinCoverageMs: MOVING_MIN_COVERAGE_MS, canonicalEmotion, pair };
})(window);
