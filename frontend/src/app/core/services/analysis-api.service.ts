import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { AnalysisResponse } from '../models/analysis.models';

@Injectable({ providedIn: 'root' })
export class AnalysisApiService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = '/api/v1';

  analyzeImage(file: File): Observable<AnalysisResponse> {
    const formData = new FormData();
    formData.append('file', file);

    return this.http.post<AnalysisResponse>(`${this.baseUrl}/analysis/image`, formData);
  }
}
