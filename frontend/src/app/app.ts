import { DecimalPipe } from '@angular/common';
import { Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

import {
  ActionUnit,
  AnalysisResponse,
  RussellPoint,
  VideoAnalysisResponse,
} from './core/models/analysis.models';
import { RUSSELL_EMOTIONS, RussellEmotion } from './core/data/russell-emotions';
import { AnalysisApiService } from './core/services/analysis-api.service';

type RecordingState = 'hidden' | 'setup' | 'countdown' | 'recording' | 'saving' | 'error';

@Component({
  selector: 'app-root',
  imports: [DecimalPipe],
  templateUrl: './app.html',
  styleUrl: './app.css'
})
export class App {
  private readonly analysisApi = inject(AnalysisApiService);
  private readonly destroyRef = inject(DestroyRef);

  // ── Imagen / Webcam ──
  protected readonly selectedFileName = signal('');
  protected readonly selectedImageUrl = signal<string | null>(null);
  protected readonly isSubmitting = signal(false);
  protected readonly errorMessage = signal('');
  protected readonly result = signal<AnalysisResponse | null>(null);
  protected readonly activeTab = signal<'image' | 'video'>('image');
  protected readonly webcamReady = signal(false);
  protected readonly capturedImageUrl = signal<string | null>(null);
  protected readonly resultTab = signal<'frame' | 'resumen'>('frame');

  // ── Video ──
  protected readonly videoResult = signal<VideoAnalysisResponse | null>(null);
  protected readonly selectedVideoFrame = signal(0);
  protected readonly videoFileName = signal('');
  protected readonly videoIntervalMs = signal(500);
  protected readonly currentFrameImageUrl = signal<string | null>(null);
  protected readonly pendingRecordingFile = signal<File | null>(null);

  // ── Grabación ──
  protected readonly recordingState = signal<RecordingState>('hidden');
  protected readonly countdownValue = signal(3);
  protected readonly recordingElapsed = signal(0);
  protected readonly stimulusFileName = signal('');
  protected readonly stimulusDuration = signal(0);
  protected readonly recordingLabel = signal('');
  protected readonly recordingError = signal('');

  private stream: MediaStream | null = null;
  private videoBlobUrl: string | null = null;
  private mediaRecorder: MediaRecorder | null = null;
  private recordedChunks: Blob[] = [];
  private recordingTimer: ReturnType<typeof setInterval> | null = null;
  private stimulusBlobUrl: string | null = null;

  constructor() {
    this.destroyRef.onDestroy(() => {
      this.stopWebcam();
      if (this.videoBlobUrl) URL.revokeObjectURL(this.videoBlobUrl);
      if (this.stimulusBlobUrl) URL.revokeObjectURL(this.stimulusBlobUrl);
      this._stopRecordingResources();
    });
  }

  // ------------------------------------------------------------------
  // Pestaña Archivo
  // ------------------------------------------------------------------

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0] ?? null;

    this.result.set(null);
    this.videoResult.set(null);
    this.errorMessage.set('');
    this.selectedFileName.set(file?.name ?? '');
    this.selectedImageUrl.set(null);
    this.capturedImageUrl.set(null);

    // Apagar cámara si estaba activa.
    this.stopWebcam();
    this.webcamReady.set(false);

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

  switchToImage(activateCam: boolean): void {
    this.activeTab.set('image');
    this.capturedImageUrl.set(null);
    if (!activateCam) {
      this.stopWebcam();
    } else {
      setTimeout(() => {
        const video = document.querySelector('.image-webcam') as HTMLVideoElement | null;
        if (video) this.startWebcam(video);
      }, 0);
    }
  }

  startWebcam(video: HTMLVideoElement): void {
    if (this.stream) return;

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
    this.capturedImageUrl.set(canvas.toDataURL('image/jpeg', 0.95));

    canvas.toBlob((blob) => {
      if (!blob) {
        this.errorMessage.set('No se pudo generar la imagen desde la camara.');
        return;
      }
      const file = new File([blob], 'webcam.jpg', { type: 'image/jpeg' });
      this.analyzeFile(file);
    }, 'image/jpeg', 0.95);
    this.stopWebcam();
  }

  // ------------------------------------------------------------------
  // Pestaña Video
  // ------------------------------------------------------------------

  switchToVideo(): void {
    this.activeTab.set('video');
    this.capturedImageUrl.set(null);
    this.stopWebcam();
  }

  onVideoSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0] ?? null;

    this.result.set(null);
    this.videoResult.set(null);
    this.selectedVideoFrame.set(0);
    this.errorMessage.set('');
    this.videoFileName.set(file?.name ?? '');
    this.currentFrameImageUrl.set(null);
    this.pendingRecordingFile.set(null);

    // Liberar blob URL anterior y crear uno nuevo.
    if (this.videoBlobUrl) URL.revokeObjectURL(this.videoBlobUrl);
    this.videoBlobUrl = file ? URL.createObjectURL(file) : null;
  }

  submitVideo(input: HTMLInputElement): void {
    const file = input.files?.[0] ?? this.pendingRecordingFile();

    if (!file) {
      this.errorMessage.set('Selecciona un video antes de enviar.');
      return;
    }

    this.isSubmitting.set(true);
    this.errorMessage.set('');
    this.videoResult.set(null);

    this.analysisApi.analyzeVideo(file, this.videoIntervalMs()).pipe(
      takeUntilDestroyed(this.destroyRef)
    ).subscribe({
      next: (response) => {
        this.videoResult.set(response);
        this.selectedVideoFrame.set(0);
        this.isSubmitting.set(false);
        setTimeout(() => this._captureFrameImage(), 0);
      },
      error: () => {
        this.errorMessage.set('No se pudo analizar el video. Verifica que el backend este en ejecucion.');
        this.isSubmitting.set(false);
      }
    });
  }

  selectVideoFrame(index: number): void {
    this.selectedVideoFrame.set(index);
    this._captureFrameImage();
  }

  /** Captura la imagen del frame actual del video usando el blob URL. */
  private _captureFrameImage(): void {
    const vr = this.videoResult();
    const timestampMs = vr?.frames[this.selectedVideoFrame()]?.timestampMs;
    if (!this.videoBlobUrl || timestampMs == null) return;

    const video = document.createElement('video');
    video.muted = true;
    video.src = this.videoBlobUrl;

    video.addEventListener('loadedmetadata', () => {
      video.currentTime = timestampMs / 1000;
    });

    video.addEventListener('seeked', () => {
      const canvas = document.createElement('canvas');
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;
      ctx.drawImage(video, 0, 0);
      this.currentFrameImageUrl.set(canvas.toDataURL('image/jpeg', 0.85));
      video.remove();
    });

    video.load();
  }

  // ------------------------------------------------------------------
  // Modal de grabación
  // ------------------------------------------------------------------

  openRecordingModal(): void {
    this.recordingState.set('setup');
    this.stimulusFileName.set('');
    this.recordingLabel.set('');
    this.recordingError.set('');
  }

  cancelRecording(): void {
    this._stopRecordingResources();
    this.recordingState.set('hidden');
  }

  onStimulusSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0] ?? null;
    this.stimulusFileName.set(file?.name ?? '');
    if (this.stimulusBlobUrl) URL.revokeObjectURL(this.stimulusBlobUrl);
    this.stimulusBlobUrl = file ? URL.createObjectURL(file) : null;
  }

  async startRecording(input: HTMLInputElement): Promise<void> {
    const stimulusFile = input.files?.[0];
    if (!stimulusFile) return;

    // Countdown 3-2-1
    this.recordingState.set('countdown');
    for (let i = 3; i >= 1; i--) {
      this.countdownValue.set(i);
      await new Promise(r => setTimeout(r, 1000));
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      this.stream = stream;

      // Webcam preview
      setTimeout(() => {
        const preview = document.querySelector('.recording-webcam') as HTMLVideoElement | null;
        if (preview) { preview.srcObject = stream; preview.play(); }
      }, 0);

      // Reproducir estímulo
      setTimeout(() => {
        const stim = document.querySelector('.recording-stimulus') as HTMLVideoElement | null;
        if (stim && this.stimulusBlobUrl) {
          stim.src = this.stimulusBlobUrl;
          stim.play();
        }
      }, 0);

      // Iniciar grabación MediaRecorder en MP4 (compatible con OpenCV).
      this.recordedChunks = [];
      const mimeType = MediaRecorder.isTypeSupported('video/mp4')
        ? 'video/mp4'
        : 'video/webm; codecs=vp8';
      this.mediaRecorder = new MediaRecorder(stream, { mimeType });
      this.mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) this.recordedChunks.push(e.data); };
      this.mediaRecorder.onstop = () => this._onRecordingStopped();
      this.mediaRecorder.start();

      // Timer
      this.recordingElapsed.set(0);
      this.recordingTimer = setInterval(() => {
        this.recordingElapsed.update(v => v + 1);
      }, 1000);

      this.recordingState.set('recording');
    } catch (err: any) {
      this.recordingState.set('error');
      this.recordingError.set(err?.name === 'NotAllowedError'
        ? 'Permiso de cámara denegado.'
        : 'No se pudo acceder a la cámara.');
    }
  }

  onStimulusReady(video: HTMLVideoElement): void {
    this.stimulusDuration.set(Math.round(video.duration || 0));
  }

  onStimulusEnded(): void {
    if (this.recordingState() === 'recording') {
      this.stopRecording();
    }
  }

  protected stopRecording(): void {
    if (this.recordingTimer) { clearInterval(this.recordingTimer); this.recordingTimer = null; }
    if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
      this.mediaRecorder.stop();
    } else {
      this._stopRecordingResources();
    }
  }

  private _onRecordingStopped(): void {
    this._stopRecordingResources();
    const blob = new Blob(this.recordedChunks, { type: 'video/mp4' });
    const file = new File([blob], 'recording.mp4', { type: 'video/mp4' });

    // Guardar la grabación en disco.
    this.recordingState.set('saving');
    this.analysisApi.saveRecording(file, this.recordingLabel()).pipe(
      takeUntilDestroyed(this.destroyRef)
    ).subscribe({
      next: () => {
        this.recordingState.set('hidden');
        // Cargar el video grabado como si lo hubiera seleccionado el usuario.
        this.pendingRecordingFile.set(file);
        if (this.videoBlobUrl) URL.revokeObjectURL(this.videoBlobUrl);
        this.videoBlobUrl = URL.createObjectURL(file);
        this.activeTab.set('video');
        this.result.set(null);
        this.videoResult.set(null);
        this.selectedVideoFrame.set(0);
        this.videoFileName.set(file.name);
        this.isSubmitting.set(false);
        this.errorMessage.set('');
      },
      error: () => {
        this.recordingState.set('error');
        this.recordingError.set('No se pudo guardar la grabación.');
      }
    });
  }

  private _stopRecordingResources(): void {
    if (this.recordingTimer) { clearInterval(this.recordingTimer); this.recordingTimer = null; }
    this.stream?.getTracks().forEach(t => t.stop());
    this.stream = null;
    this.mediaRecorder = null;
  }

  /** Retorna el AnalysisResponse activo según el tab actual. */
  currentAnalysis(): AnalysisResponse | null {
    if (this.activeTab() === 'video') {
      const vr = this.videoResult();
      if (vr && vr.frames.length > 0) {
        return vr.frames[this.selectedVideoFrame()]?.analysis ?? null;
      }
      return null;
    }
    return this.result();
  }

  /** Puntos de la trayectoria del video sobre el plano de Russell. */
  trajectoryPoints(): RussellPoint[] {
    return this.videoResult()?.summary?.russellPoints ?? [];
  }

  /** String con coordenadas para el SVG polyline que conecta los puntos. */
  trajectoryLinePoints(): string {
    return this.trajectoryPoints()
      .map(p => {
        const x = (p.x + 1) * 50;
        const y = 100 - ((p.y + 1) * 50);
        return `${x},${y}`;
      })
      .join(' ');
  }

  /** String con coordenadas para el SVG de un timeline (valencia o arousal). */
  timelineLinePoints(values: number[]): string {
    if (values.length <= 1) return '';
    const maxX = values.length - 1;
    return values
      .map((v, i) => {
        const x = 8 + (i / maxX) * 84;
        const y = 10 - (v * 8);
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(' ');
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
    const analysis = this.currentAnalysis();
    const probabilities = analysis?.emotionProbabilities ?? {};
    return Object.entries(probabilities).map(([name, value]) => ({ name, value }));
  }

  actionUnitEntries(): Array<{ name: string; value: ActionUnit }> {
    const analysis = this.currentAnalysis();
    const actionUnits = analysis?.actionUnits ?? {};
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

  referenceEmotions(): RussellEmotion[] {
    return RUSSELL_EMOTIONS;
  }

  labelPositions(): Array<{ label: string; left: number; top: number }> {
    return RUSSELL_EMOTIONS.map(e => {
      const r = Math.hypot(e.x, e.y);
      const angle = Math.atan2(e.y, e.x);
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

  nearestEmotions(): RussellEmotion[] {
    const point = this.currentAnalysis()?.russellPoint;
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
