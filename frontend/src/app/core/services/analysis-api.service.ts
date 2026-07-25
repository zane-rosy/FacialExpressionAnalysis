import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { AnalysisResponse, RecordingSavedResponse, VideoAnalysisResponse } from '../models/analysis.models';

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

  saveRecording(file: File, label: string): Observable<RecordingSavedResponse> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('label', label);
    return this.http.post<RecordingSavedResponse>(`${this.baseUrl}/recordings/save`, formData);
  }
}
