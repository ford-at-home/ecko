/**
 * Audio Recording Utility for Echoes App
 * Handles browser-based audio recording with WebRTC
 */

export class AudioRecorder {
  constructor() {
    this.mediaRecorder = null;
    this.audioStream = null;
    this.recordedChunks = [];
    this.isRecording = false;
    this.onDataAvailable = null;
    this.onStop = null;
    this.onError = null;
    
    // Configuration
    this.config = {
      audio: {
        channelCount: 2,
        sampleRate: 44100,
        sampleSize: 16,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
      mimeType: this.getSupportedMimeType(),
      minDuration: 10000, // 10 seconds
      maxDuration: 30000, // 30 seconds
    };
  }

  /**
   * Get supported audio MIME type for recording
   */
  getSupportedMimeType() {
    const types = [
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/mp4',
      'audio/wav',
    ];
    
    for (const type of types) {
      if (MediaRecorder.isTypeSupported(type)) {
        return type;
      }
    }
    
    return 'audio/webm'; // fallback
  }

  /**
   * Initialize audio recording
   */
  async initialize() {
    try {
      // Check for MediaRecorder support
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error('MediaRecorder not supported in this browser');
      }

      // Request microphone access
      this.audioStream = await navigator.mediaDevices.getUserMedia({
        audio: this.config.audio,
        video: false,
      });

      // Create MediaRecorder instance
      this.mediaRecorder = new MediaRecorder(this.audioStream, {
        mimeType: this.config.mimeType,
      });

      // Set up event listeners
      this.setupEventListeners();

      console.log('Audio recorder initialized successfully');
      return true;
    } catch (error) {
      console.error('Failed to initialize audio recorder:', error);
      if (this.onError) {
        this.onError(error);
      }
      throw error;
    }
  }

  /**
   * Set up MediaRecorder event listeners
   */
  setupEventListeners() {
    this.mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        this.recordedChunks.push(event.data);
        if (this.onDataAvailable) {
          this.onDataAvailable(event.data);
        }
      }
    };

    this.mediaRecorder.onstop = () => {
      const audioBlob = new Blob(this.recordedChunks, {
        type: this.config.mimeType,
      });
      
      if (this.onStop) {
        this.onStop(audioBlob);
      }
      
      this.recordedChunks = [];
    };

    this.mediaRecorder.onerror = (event) => {
      console.error('MediaRecorder error:', event.error);
      if (this.onError) {
        this.onError(event.error);
      }
    };
  }

  /**
   * Start recording audio
   */
  async startRecording() {
    try {
      if (!this.mediaRecorder) {
        await this.initialize();
      }

      if (this.isRecording) {
        throw new Error('Recording already in progress');
      }

      // Clear previous recording
      this.recordedChunks = [];
      
      // Start recording
      this.mediaRecorder.start(1000); // Collect data every 1 second
      this.isRecording = true;

      // Set maximum recording duration
      setTimeout(() => {
        if (this.isRecording) {
          this.stopRecording();
        }
      }, this.config.maxDuration);

      console.log('Recording started');
      return true;
    } catch (error) {
      console.error('Failed to start recording:', error);
      throw error;
    }
  }

  /**
   * Stop recording audio
   */
  stopRecording() {
    try {
      if (!this.isRecording || !this.mediaRecorder) {
        throw new Error('No recording in progress');
      }

      this.mediaRecorder.stop();
      this.isRecording = false;

      console.log('Recording stopped');
      return true;
    } catch (error) {
      console.error('Failed to stop recording:', error);
      throw error;
    }
  }

  /**
   * Get recording duration
   */
  getRecordingDuration() {
    if (!this.isRecording) {
      return 0;
    }
    
    // This would need to be tracked during recording
    // For now, return estimated duration based on chunks
    return this.recordedChunks.length * 1000; // Rough estimate
  }

  /**
   * Check if minimum duration requirement is met
   */
  isMinimumDurationMet() {
    return this.getRecordingDuration() >= this.config.minDuration;
  }

  /**
   * Clean up resources
   */
  cleanup() {
    try {
      if (this.mediaRecorder && this.isRecording) {
        this.mediaRecorder.stop();
      }

      if (this.audioStream) {
        this.audioStream.getTracks().forEach(track => track.stop());
        this.audioStream = null;
      }

      this.mediaRecorder = null;
      this.isRecording = false;
      this.recordedChunks = [];

      console.log('Audio recorder cleaned up');
    } catch (error) {
      console.error('Error during cleanup:', error);
    }
  }

  /**
   * Convert audio blob to base64
   */
  async blobToBase64(blob) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result.split(',')[1]);
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  }

  /**
   * Get audio file information
   */
  getAudioInfo(blob) {
    return {
      size: blob.size,
      type: blob.type,
      duration: this.getRecordingDuration(),
    };
  }

  /**
   * Set event callbacks
   */
  setCallbacks({ onDataAvailable, onStop, onError }) {
    this.onDataAvailable = onDataAvailable;
    this.onStop = onStop;
    this.onError = onError;
  }

  /**
   * Check browser compatibility
   */
  static isSupported() {
    return !!(
      navigator.mediaDevices &&
      navigator.mediaDevices.getUserMedia &&
      window.MediaRecorder
    );
  }

  /**
   * Request microphone permissions
   */
  static async requestPermissions() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach(track => track.stop());
      return true;
    } catch (error) {
      console.error('Microphone permission denied:', error);
      return false;
    }
  }
}

// Audio visualization utility
export class AudioVisualizer {
  constructor(canvasElement) {
    this.canvas = canvasElement;
    this.ctx = this.canvas.getContext('2d');
    this.audioContext = null;
    this.analyser = null;
    this.dataArray = null;
    this.animationId = null;
  }

  /**
   * Initialize audio visualization
   */
  async initialize(audioStream) {
    try {
      this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
      this.analyser = this.audioContext.createAnalyser();
      
      const source = this.audioContext.createMediaStreamSource(audioStream);
      source.connect(this.analyser);
      
      this.analyser.fftSize = 256;
      const bufferLength = this.analyser.frequencyBinCount;
      this.dataArray = new Uint8Array(bufferLength);
      
      this.draw();
    } catch (error) {
      console.error('Failed to initialize audio visualizer:', error);
    }
  }

  /**
   * Draw audio waveform
   */
  draw() {
    this.animationId = requestAnimationFrame(() => this.draw());
    
    this.analyser.getByteFrequencyData(this.dataArray);
    
    this.ctx.fillStyle = 'rgb(0, 0, 0)';
    this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    
    const barWidth = (this.canvas.width / this.dataArray.length) * 2.5;
    let barHeight;
    let x = 0;
    
    for (let i = 0; i < this.dataArray.length; i++) {
      barHeight = this.dataArray[i] / 255 * this.canvas.height;
      
      this.ctx.fillStyle = `rgb(${barHeight + 100}, 50, 50)`;
      this.ctx.fillRect(x, this.canvas.height - barHeight, barWidth, barHeight);
      
      x += barWidth + 1;
    }
  }

  /**
   * Stop visualization
   */
  stop() {
    if (this.animationId) {
      cancelAnimationFrame(this.animationId);
      this.animationId = null;
    }
    
    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }
  }
}

export default AudioRecorder;