import { DecimalPipe } from '@angular/common';
import { Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

import { ActionUnit, AnalysisResponse } from './core/models/analysis.models';
import { RUSSELL_EMOTIONS, RussellEmotion } from './core/data/russell-emotions';
import { AnalysisApiService } from './core/services/analysis-api.service';

@Component({
  selector: 'app-root',
  imports: [DecimalPipe],
  templateUrl: './app.html',
  styleUrl: './app.css'
})
export class App {
  private readonly analysisApi = inject(AnalysisApiService);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly selectedFileName = signal('');
  protected readonly selectedImageUrl = signal<string | null>(null);
  protected readonly isSubmitting = signal(false);
  protected readonly errorMessage = signal('');
  protected readonly result = signal<AnalysisResponse | null>(null);
  protected readonly activeTab = signal<'upload' | 'webcam'>('upload');
  protected readonly webcamReady = signal(false);
  protected readonly capturedImageUrl = signal<string | null>(null);

  private stream: MediaStream | null = null;

  constructor() {
    // Liberar el stream de la cámara al destruir el componente.
    this.destroyRef.onDestroy(() => this.stopWebcam());
  }

  // ------------------------------------------------------------------
  // Pestaña Archivo
  // ------------------------------------------------------------------

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0] ?? null;

    this.result.set(null);
    this.errorMessage.set('');
    this.selectedFileName.set(file?.name ?? '');
    this.selectedImageUrl.set(null);

    if (file) {
      const reader = new FileReader();
      reader.onload = () => this.selectedImageUrl.set(reader.result as string);
      reader.readAsDataURL(file);
    }
  }

  submit(input: HTMLInputElement): void {
    const file = input.files?.[0] ?? null;

    if (!file) {
      this.errorMessage.set('Selecciona una imagen antes de enviar.');
      return;
    }

    this.analyzeFile(file);
  }

  // ------------------------------------------------------------------
  // Pestaña Webcam
  // ------------------------------------------------------------------

  switchToWebcam(): void {
    this.activeTab.set('webcam');
    // Esperar a que Angular renderice el @else block y luego obtener el <video>.
    setTimeout(() => {
      const video = document.querySelector('.webcam-video') as HTMLVideoElement | null;
      if (video) this.startWebcam(video);
    }, 0);
  }

  switchToUpload(): void {
    this.activeTab.set('upload');
    this.capturedImageUrl.set(null);
    this.stopWebcam();
  }

  startWebcam(video: HTMLVideoElement): void {
    if (this.stream) return; // ya está corriendo

    navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } })
      .then((stream) => {
        this.stream = stream;
        video.srcObject = stream;
        video.play().then(() => this.webcamReady.set(true));
      })
      .catch((err) => {
        this.webcamReady.set(false);
        if (err.name === 'NotAllowedError') {
          this.errorMessage.set('Permiso de camara denegado. Concedelo en la configuracion del navegador.');
        } else {
          this.errorMessage.set('No se pudo acceder a la camara. Verifica que este conectada.');
        }
      });
  }

  stopWebcam(): void {
    this.stream?.getTracks().forEach(track => track.stop());
    this.stream = null;
    this.webcamReady.set(false);
  }

  captureFromWebcam(video: HTMLVideoElement): void {
    if (!this.webcamReady()) {
      this.errorMessage.set('La camara no esta lista todavia.');
      return;
    }

    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const ctx = canvas.getContext('2d');
    if (!ctx) {
      this.errorMessage.set('No se pudo capturar el fotograma.');
      return;
    }

    ctx.drawImage(video, 0, 0);

    // Guardar un data URL para que el usuario vea qué frame se capturó.
    this.capturedImageUrl.set(canvas.toDataURL('image/jpeg', 0.95));

    canvas.toBlob((blob) => {
      if (!blob) {
        this.errorMessage.set('No se pudo generar la imagen desde la camara.');
        return;
      }
      const file = new File([blob], 'webcam.jpg', { type: 'image/jpeg' });
      this.analyzeFile(file);
    }, 'image/jpeg', 0.95);
  }

  // ------------------------------------------------------------------
  // Compartido
  // ------------------------------------------------------------------

  private analyzeFile(file: File): void {
    this.isSubmitting.set(true);
    this.errorMessage.set('');

    this.analysisApi.analyzeImage(file).pipe(
      takeUntilDestroyed(this.destroyRef)
    ).subscribe({
      next: (response) => {
        this.result.set(response);
        this.isSubmitting.set(false);
      },
      error: () => {
        this.errorMessage.set('No se pudo analizar la imagen. Verifica que el backend este en ejecucion.');
        this.isSubmitting.set(false);
      }
    });
  }

  emotionEntries(): Array<{ name: string; value: number }> {
    const probabilities = this.result()?.emotionProbabilities ?? {};
    return Object.entries(probabilities).map(([name, value]) => ({ name, value }));
  }

  actionUnitEntries(): Array<{ name: string; value: ActionUnit }> {
    const actionUnits = this.result()?.actionUnits ?? {};
    return Object.entries(actionUnits).map(([name, value]) => ({ name, value }));
  }

  maxProbability(): number {
    const entries = this.emotionEntries();
    if (entries.length === 0) return 0;
    return Math.max(...entries.map(e => e.value));
  }

  // ------------------------------------------------------------------
  // Plano de Russell — puntos de referencia
  // ------------------------------------------------------------------

  /** Los 28 puntos de referencia del modelo circumplejo. */
  referenceEmotions(): RussellEmotion[] {
    return RUSSELL_EMOTIONS;
  }

  /**
   * Posición de la etiqueta para cada emoción, proyectada radialmente
   * hacia afuera (radio fijo 1.12) para formar un anillo externo uniforme.
   */
  labelPositions(): Array<{ label: string; left: number; top: number }> {
    return RUSSELL_EMOTIONS.map(e => {
      const r = Math.hypot(e.x, e.y);
      const angle = Math.atan2(e.y, e.x);
      // Project label slightly outward from the dot, capped at 0.90 to stay inside the circle.
      const labelR = Math.min(r * 1.10, 0.90);
      const lx = labelR * Math.cos(angle);
      const ly = labelR * Math.sin(angle);
      return {
        label: e.label,
        left: (lx + 1) * 50,
        top: 100 - ((ly + 1) * 50),
      };
    });
  }

  /** Las 3 emociones de referencia más cercanas al punto del usuario. */
  nearestEmotions(): RussellEmotion[] {
    const point = this.result()?.russellPoint;
    if (!point) return [];

    return RUSSELL_EMOTIONS
      .map(e => ({
        emotion: e,
        dist: Math.hypot(e.x - point.x, e.y - point.y),
      }))
      .sort((a, b) => a.dist - b.dist)
      .slice(0, 3)
      .map(e => e.emotion);
  }
}
