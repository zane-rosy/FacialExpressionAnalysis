import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { AnalysisResponse, RecordingSavedResponse, StimulusMetadata, VideoAnalysisResponse } from '../models/analysis.models';

@Injectable({ providedIn: 'root' })
export class AnalysisApiService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = '/api/v1';

  analyzeImage(file: File): Observable<AnalysisResponse> {
    const formData = new FormData();
    formData.append('file', file);

    return this.http.post<AnalysisResponse>(`${this.baseUrl}/analysis/image`, formData);
  }

  analyzeVideo(file: File, intervalMs: number): Observable<VideoAnalysisResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const params = new HttpParams().set('interval_ms', intervalMs.toString());

    return this.http.post<VideoAnalysisResponse>(
      `${this.baseUrl}/analysis/video`,
      formData,
      { params },
    );
  }

  getStimulusMetadata(filename: string): Observable<StimulusMetadata | null> {
    const params = new HttpParams().set('filename', filename);
    return this.http.get<StimulusMetadata | null>(`${this.baseUrl}/analysis/stimuli/metadata`, { params });
  }

  saveRecording(file: File, label: string, participantId: string, stimulus: { filename: string; clipId: string; sourceTitle: string; description: string } | null): Observable<RecordingSavedResponse> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('label', label);
    formData.append('participant_id', participantId);
    if (stimulus) {
      formData.append('stimulus_clip_id', stimulus.clipId);
      formData.append('stimulus_source_title', stimulus.sourceTitle);
      formData.append('stimulus_description', stimulus.description);
    }
    return this.http.post<RecordingSavedResponse>(`${this.baseUrl}/recordings/save`, formData);
  }

  updateRecordingMetadata(filename: string, avgValence: number, avgArousal: number, dominantEmotion: string, framesEvaluated: number): Observable<void> {
    return this.http.patch<void>(`${this.baseUrl}/recordings/${encodeURIComponent(filename)}/metadata`, {
      avgValence,
      avgArousal,
      dominantEmotion,
      framesEvaluated,
    });
  }
}
