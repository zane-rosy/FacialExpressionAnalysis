#!/usr/bin/env node

/*
 * Procesamiento batch de resultados ya generados.
 * No ejecuta OpenFace, MorphCast ni procesa los frames del video: solo lee
 * los JSON, consulta la metadata de duración con ffprobe y aplica la lógica
 * compartida de frontend/public/analysis-utils.js.
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { spawnSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const DEFAULT_OUTPUT_DIR = path.join(ROOT, 'batch-output');

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    if (!token.startsWith('--')) continue;
    const name = token.slice(2);
    args[name] = argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[++i] : true;
  }
  return args;
}

function usage() {
  console.log(`Uso:
  node scripts/process-batch.js --input-dir <Resultados> --video-dir <recordings> [opciones]

Opciones:
  --devo <tabla.csv|tabla.json>   Valores DEVO por identificador de estímulo
  --output-dir <directorio>       Directorio de salida (por defecto: ./batch-output)
  --filter <texto>                Procesa solo reacciones cuyo nombre contenga el texto
  --no-segments-csv               No generar el CSV detallado por segmento
  --help                          Mostrar esta ayuda

Ejemplo de validación:
  node scripts/process-batch.js --input-dir "C:/Users/charl/Desktop/Resultados" --video-dir "./recordings" --filter 96.1`);
}

function walkFiles(directory, extension) {
  if (!directory || !fs.existsSync(directory)) return [];
  const result = [];
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) result.push(...walkFiles(fullPath, extension));
    else if (!extension || path.extname(entry.name).toLowerCase() === extension) result.push(fullPath);
  }
  return result;
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function canonicalBase(filePath) {
  return path.basename(filePath, path.extname(filePath))
    .toLowerCase()
    .replace(/^morphcast[-_]/, '')
    .replace(/[-_]frames$/, '')
    .replace(/[-_](system|proposed|emotion|results)$/, '');
}

function parseIdentity(filePath, payload) {
  const name = path.basename(filePath);
  const parentDirectory = path.basename(path.dirname(filePath));
  const source = payload?.stimulusClipId || payload?.stimulusId || payload?.stimulus || '';
  const participant = payload?.participantId || payload?.participant || '';
  const match = name.match(/(?:^|[_-])devo-(\d+)[_-](\d+)/i);
  const parsedStimulus = match ? `${match[1]}.${match[2]}` : '';
  const stimulusId = String(source || parsedStimulus).trim().replace(/^devo[-_]/i, '').replace(/^(\d+)[_-](\d+)$/, '$1.$2') || null;
  const filenameParticipant = name.match(/^(?:morphcast[-_])?reaccion_([^_]+(?:_[FM])?)_/i)?.[1] || '';
  const participantId = String(participant || parentDirectory || filenameParticipant).trim() || null;
  return { participantId, stimulusId };
}

function classifyJson(payload) {
  if (Array.isArray(payload)) return 'morphcast';
  if (Array.isArray(payload?.frames)) return 'system';
  if (Array.isArray(payload?.results)) return 'morphcast';
  return null;
}

function normalizePayload(payload, kind, U) {
  if (kind === 'system') return U.normalizeSystem(payload);
  if (kind === 'morphcast') return U.normalizeMorph(Array.isArray(payload) ? payload : payload.results);
  return [];
}

function number(value) {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function meanError(pairs, key) {
  const values = pairs.map(pair => {
    const left = number(pair.morph[key]);
    const right = number(pair.system[key]);
    return left != null && right != null ? Math.abs(left - right) : null;
  }).filter(value => value != null);
  return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;
}

function comparison(pairs, U) {
  const comparable = pairs.filter(pair => U.canonicalEmotion(pair.morph.dominantEmotion) && U.canonicalEmotion(pair.system.dominantEmotion));
  const matches = comparable.filter(pair => U.canonicalEmotion(pair.morph.dominantEmotion) === U.canonicalEmotion(pair.system.dominantEmotion)).length;
  return {
    temporalPairs: pairs.length,
    maeValence: meanError(pairs, 'valence'),
    maeArousal: meanError(pairs, 'arousal'),
    categoricalMatches: matches,
    categoricalComparablePairs: comparable.length,
    categoricalAccuracy: comparable.length ? matches / comparable.length : null
  };
}

function segmentResult(rows, durationMs, U) {
  return U.segments(rows, durationMs).map(segment => ({
    segment: segment.index + 1,
    startMs: segment.from,
    endMs: segment.to,
    summary: U.summarize(segment.rows)
  }));
}

function movingResult(rows, durationMs, U) {
  const result = U.movingWindowAnalysis(rows, durationMs);
  const simplify = window => window ? {
    startMs: window.startMs,
    endMs: window.endMs,
    n: window.n,
    firstTimestampMs: window.firstTimestampMs,
    lastTimestampMs: window.lastTimestampMs,
    coverageMs: window.coverageMs,
    valence: window.valence,
    arousal: window.arousal,
    categorical: window.categorical,
    dimensional: window.dimensional,
    affects38: window.affects38,
    affects98: window.affects98
  } : null;
  return {
    windowMs: U.movingWindowMs,
    stepMs: U.movingStepMs,
    minSampleRatio: U.movingMinSampleRatio,
    minCoverageMs: U.movingMinCoverageMs,
    totalWindows: result.windows.length,
    validWindows: result.eligibleWindows.length,
    validWindowPercentage: result.windows.length ? result.eligibleWindows.length / result.windows.length * 100 : 0,
    medianIntervalMs: result.medianIntervalMs,
    expectedSamples: result.expectedSamples,
    minSamples: result.minSamples,
    maximumExcitation: simplify(result.maximum),
    minimumExcitation: simplify(result.minimum)
  };
}

function findDuration(videoPath) {
  if (!videoPath) return null;
  const probe = spawnSync('ffprobe', [
    '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', videoPath
  ], { encoding: 'utf8', windowsHide: true });
  if (probe.status === 0) {
    const seconds = Number.parseFloat(probe.stdout.trim());
    if (Number.isFinite(seconds) && seconds > 0) return seconds * 1000;
  }
  // En Windows, ffprobe puede estar disponible mediante una app de WinGet
  // pero no quedar expuesto en el PATH heredado por Node. Como fallback se
  // consulta únicamente la metadata del contenedor con OpenCV, sin leer los
  // frames del video.
  const pythonCode = 'import cv2,sys; c=cv2.VideoCapture(sys.argv[1]); fps=c.get(cv2.CAP_PROP_FPS); frames=c.get(cv2.CAP_PROP_FRAME_COUNT); print((frames/fps) if fps and fps > 0 else "")';
  const python = spawnSync('python', ['-c', pythonCode, videoPath], { encoding: 'utf8', windowsHide: true });
  const seconds = Number.parseFloat((python.stdout || '').trim());
  return Number.isFinite(seconds) && seconds > 0 ? seconds * 1000 : null;
}

function csvValue(value) {
  if (value == null) return '';
  const text = typeof value === 'object' ? JSON.stringify(value) : String(value);
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function writeCsv(filePath, rows) {
  const columns = [...new Set(rows.flatMap(row => Object.keys(row)))];
  const lines = [columns.join(',')];
  for (const row of rows) lines.push(columns.map(column => csvValue(row[column])).join(','));
  fs.writeFileSync(filePath, `${lines.join('\n')}\n`, 'utf8');
}

function flattenWindow(prefix, window) {
  if (!window) return { [`${prefix}_available`]: false };
  return {
    [`${prefix}_available`]: true,
    [`${prefix}_startMs`]: window.startMs,
    [`${prefix}_endMs`]: window.endMs,
    [`${prefix}_n`]: window.n,
    [`${prefix}_firstTimestampMs`]: window.firstTimestampMs,
    [`${prefix}_lastTimestampMs`]: window.lastTimestampMs,
    [`${prefix}_coverageMs`]: window.coverageMs,
    [`${prefix}_valence`]: window.valence,
    [`${prefix}_arousal`]: window.arousal,
    [`${prefix}_categorical`]: window.categorical,
    [`${prefix}_dimensional`]: window.dimensional,
    [`${prefix}_affects38`]: window.affects38,
    [`${prefix}_affects98`]: window.affects98
  };
}

function flattenSummary(prefix, summary) {
  return {
    [`${prefix}_n`]: summary?.n ?? null,
    [`${prefix}_valence`]: summary?.valence ?? null,
    [`${prefix}_arousal`]: summary?.arousal ?? null,
    [`${prefix}_categorical`]: summary?.categorical ?? null,
    [`${prefix}_dimensional`]: summary?.dimensional ?? null,
    [`${prefix}_affects38`]: summary?.affects38 ?? null,
    [`${prefix}_affects98`]: summary?.affects98 ?? null
  };
}

function readDevo(filePath) {
  if (!filePath) return new Map();
  const content = fs.readFileSync(filePath, 'utf8');
  if (filePath.toLowerCase().endsWith('.json')) {
    const json = JSON.parse(content);
    const rows = Array.isArray(json) ? json : json.rows || json.data || [];
    return new Map(rows.map(row => [String(row.stimulusId ?? row.stimulus ?? row.id ?? row.clipId), row]));
  }
  const lines = content.split(/\r?\n/).filter(Boolean);
  if (!lines.length) return new Map();
  const delimiter = lines[0].includes(';') ? ';' : ',';
  const parseLine = line => line.split(delimiter).map(value => value.trim().replace(/^"|"$/g, ''));
  const headers = parseLine(lines[0]).map(value => value.toLowerCase());
  const find = names => names.map(name => headers.indexOf(name)).find(index => index >= 0);
  const idIndex = find(['stimulusid', 'stimulus_id', 'stimulus', 'id', 'clipid']);
  const vIndex = find(['devo_v', 'devo_valence', 'valence', 'v']);
  const eIndex = find(['devo_e', 'devo_arousal', 'arousal', 'excitement', 'e']);
  const map = new Map();
  for (const line of lines.slice(1)) {
    const values = parseLine(line);
    const id = idIndex == null ? null : values[idIndex];
    if (id) map.set(id, { valence: Number(values[vIndex]), arousal: Number(values[eIndex]) });
  }
  return map;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) return usage();
  const inputDir = path.resolve(String(args['input-dir'] || ''));
  const videoDir = path.resolve(String(args['video-dir'] || path.join(ROOT, 'recordings')));
  const outputDir = path.resolve(String(args['output-dir'] || DEFAULT_OUTPUT_DIR));
  if (!inputDir || !fs.existsSync(inputDir)) throw new Error(`No existe --input-dir: ${inputDir}`);
  fs.mkdirSync(outputDir, { recursive: true });

  const context = { window: {} };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(ROOT, 'frontend/public/analysis-utils.js'), 'utf8'), context);
  const U = context.window.AnalysisUtils;
  const devo = readDevo(args.devo ? path.resolve(String(args.devo)) : null);
  const jsonFiles = walkFiles(inputDir, '.json').filter(file => !file.startsWith(outputDir));
  const videos = new Map(walkFiles(videoDir, '.mp4').map(file => [path.basename(file, path.extname(file)).toLowerCase(), file]));
  const groups = new Map();
  const warnings = [];

  for (const file of jsonFiles) {
    try {
      const payload = readJson(file);
      const kind = classifyJson(payload);
      if (!kind) { warnings.push({ type: 'unsupported_json', file, message: 'No contiene frames del sistema ni muestras de MorphCast.' }); continue; }
      const key = canonicalBase(file);
      const group = groups.get(key) || { key };
      group[kind] = { file, payload };
      group.identity = group.identity || parseIdentity(file, payload);
      groups.set(key, group);
    } catch (error) {
      warnings.push({ type: 'invalid_json', file, message: error.message });
    }
  }

  const detailedRows = [];
  const segmentRows = [];
  const consolidated = [];
  let errors = 0;
  let noCoverage = 0;
  let unpaired = 0;
  const filterText = args.filter ? String(args.filter).toLowerCase() : null;

  for (const group of [...groups.values()].sort((a, b) => a.key.localeCompare(b.key))) {
    if (filterText && !group.key.includes(filterText) && !group.key.includes(filterText.replaceAll('.', '_'))) continue;
    const reactionWarnings = [];
    if (!group.system) { reactionWarnings.push('Falta JSON del sistema propuesto'); unpaired += 1; }
    if (!group.morphcast) { reactionWarnings.push('Falta JSON de MorphCast'); unpaired += 1; }
    const sourceFile = group.system?.file || group.morphcast?.file;
    const base = path.basename(sourceFile || group.key, path.extname(sourceFile || group.key))
      .replace(/^morphcast[-_]/i, '').replace(/[-_]frames$/i, '');
    const payload = group.system?.payload || group.morphcast?.payload;
    const identity = group.identity || parseIdentity(sourceFile, payload);
    const video = videos.get(`${base.toLowerCase()}`) || videos.get(`${base.toLowerCase().replace(/[-_]frames$/, '')}`) || null;
    const durationMs = findDuration(video);
    if (!video) reactionWarnings.push('No se encontró el video correspondiente');
    if (!(durationMs > 0)) reactionWarnings.push('No se pudo obtener la duración real con ffprobe');
    const record = { reactionId: group.key, participantId: identity.participantId, stimulusId: identity.stimulusId, files: { system: group.system?.file || null, morphcast: group.morphcast?.file || null, video }, durationMs, warnings: reactionWarnings };
    try {
      const systemRows = group.system ? normalizePayload(group.system.payload, 'system', U) : [];
      const morphRows = group.morphcast ? normalizePayload(group.morphcast.payload, 'morphcast', U) : [];
      record.system = systemRows.length ? { nInput: systemRows.length, global: U.summarize(systemRows), segments: durationMs ? segmentResult(systemRows, durationMs, U) : [], moving: durationMs ? movingResult(systemRows, durationMs, U) : null } : null;
      record.morphcast = morphRows.length ? { nInput: morphRows.length, global: U.summarize(morphRows), segments: durationMs ? segmentResult(morphRows, durationMs, U) : [], moving: durationMs ? movingResult(morphRows, durationMs, U) : null } : null;
      if (durationMs && record.system && record.morphcast) {
        const pairs = U.pair(morphRows, systemRows);
        record.comparison = comparison(pairs, U);
      } else record.comparison = null;
      const devoRow = identity.stimulusId ? (devo.get(String(identity.stimulusId)) || devo.get(String(identity.stimulusId).replace('.', '_'))) : null;
      record.devo = devoRow ? { valence: number(devoRow.valence ?? devoRow.devoV ?? devoRow.V), arousal: number(devoRow.arousal ?? devoRow.devoE ?? devoRow.E) } : null;
      if (args.devo && !record.devo) reactionWarnings.push('No se encontró un valor DEVO para el estímulo');
      if ((record.system?.moving && (!record.system.moving.maximumExcitation || !record.system.moving.minimumExcitation)) || (record.morphcast?.moving && (!record.morphcast.moving.maximumExcitation || !record.morphcast.moving.minimumExcitation))) {
        noCoverage += 1;
        reactionWarnings.push('Una herramienta no tiene ventana móvil con cobertura suficiente');
      }
      for (const [tool, data] of [['system', record.system], ['morphcast', record.morphcast]]) {
        if (!data) continue;
        for (const segment of data.segments) segmentRows.push({ reactionId: group.key, participantId: identity.participantId, stimulusId: identity.stimulusId, tool, ...segment, ...flattenSummary('', segment.summary) });
      }
      const row = { reactionId: group.key, participantId: identity.participantId, stimulusId: identity.stimulusId, durationMs, systemFile: record.files.system, morphcastFile: record.files.morphcast, videoFile: video, warningCount: reactionWarnings.length, ...flattenSummary('system_global', record.system?.global), ...flattenSummary('morph_global', record.morphcast?.global), system_medianIntervalMs: record.system?.moving?.medianIntervalMs ?? null, system_expectedSamples: record.system?.moving?.expectedSamples ?? null, system_minSamples: record.system?.moving?.minSamples ?? null, system_validWindows: record.system?.moving?.validWindows ?? null, morph_medianIntervalMs: record.morphcast?.moving?.medianIntervalMs ?? null, morph_expectedSamples: record.morphcast?.moving?.expectedSamples ?? null, morph_minSamples: record.morphcast?.moving?.minSamples ?? null, morph_validWindows: record.morphcast?.moving?.validWindows ?? null, devo_valence: record.devo?.valence ?? null, devo_arousal: record.devo?.arousal ?? null, ...flattenWindow('system_max', record.system?.moving?.maximumExcitation), ...flattenWindow('system_min', record.system?.moving?.minimumExcitation), ...flattenWindow('morph_max', record.morphcast?.moving?.maximumExcitation), ...flattenWindow('morph_min', record.morphcast?.moving?.minimumExcitation), ...record.comparison };
      detailedRows.push(row);
      consolidated.push(record);
    } catch (error) {
      errors += 1;
      reactionWarnings.push(`Error procesando la reacción: ${error.message}`);
      consolidated.push(record);
    }
  }

  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const csvPath = path.join(outputDir, `batch-reactions-${timestamp}.csv`);
  const segmentsPath = path.join(outputDir, `batch-segments-${timestamp}.csv`);
  const jsonPath = path.join(outputDir, `batch-results-${timestamp}.json`);
  writeCsv(csvPath, detailedRows);
  if (!args['no-segments-csv']) writeCsv(segmentsPath, segmentRows);
  fs.writeFileSync(jsonPath, JSON.stringify({ generatedAt: new Date().toISOString(), configuration: { windowMs: U.movingWindowMs, stepMs: U.movingStepMs, minSampleRatio: U.movingMinSampleRatio, minCoverageMs: U.movingMinCoverageMs, pairToleranceMs: 250 }, reactions: consolidated, warnings }, null, 2), 'utf8');
  const missingPairs = [...groups.values()].filter(group => !group.system || !group.morphcast).length;
  console.log(JSON.stringify({ processed: consolidated.length, errors, filesWithoutPair: missingPairs, reactionsWithInsufficientCoverage: noCoverage, warnings: warnings.length, outputs: { reactionsCsv: csvPath, segmentsCsv: args['no-segments-csv'] ? null : segmentsPath, json: jsonPath } }, null, 2));
}

try { main(); } catch (error) { console.error(`ERROR: ${error.message}`); process.exitCode = 1; }
