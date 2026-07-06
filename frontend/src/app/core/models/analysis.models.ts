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
