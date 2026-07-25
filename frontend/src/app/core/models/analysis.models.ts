export interface ActionUnit {
  raw: number;
  normalized: number;
}

export interface RussellPoint {
  x: number;
  y: number;
  label: string;
}

export interface ProcessingMetadata {
  inputType: string;
  framesProcessed: number;
  mode: string;
  notes: string[];
}

export interface AnalysisResponse {
  dominantEmotion: string;
  emotionProbabilities: Record<string, number>;
  actionUnits: Record<string, ActionUnit>;
  valence: number;
  arousal: number;
  russellPoint: RussellPoint;
  processing: ProcessingMetadata;
}

// ── Modelos de video ──

export interface FrameResult {
  index: number;
  timestampMs: number;
  analysis: AnalysisResponse;
}

export interface VideoSummary {
  totalFrames: number;
  dominantEmotion: string;
  avgValence: number;
  avgArousal: number;
  valenceTimeline: number[];
  arousalTimeline: number[];
  dominantTimeline: string[];
  russellPoints: RussellPoint[];
}

export interface VideoAnalysisResponse {
  frames: FrameResult[];
  summary: VideoSummary;
  processing: ProcessingMetadata;
}

// ── Grabaciones ──

export interface RecordingSavedResponse {
  filename: string;
  path: string;
  label: string;
  recordedAt: string;
}
