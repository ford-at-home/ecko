/**
 * API Client for Echoes App
 * Handles communication with the backend API
 */

import { config, getApiUrl } from '../config';

interface ApiClientOptions {
  headers?: Record<string, string>;
  [key: string]: any;
}

interface UploadData {
  content_type: string;
  file_size: number;
  emotion: string;
  tags?: string[];
  location?: any;
}

interface PresignedUrlResponse {
  upload_url: string;
  s3_key: string;
  fields: Record<string, string>;
}

interface EchoData {
  s3_key: string;
  emotion: string;
  tags?: string[];
  location?: any;
  transcript?: string;
}

interface UploadMetadata {
  emotion: string;
  tags?: string[];
  location?: any;
  transcript?: string;
}

interface ProgressEvent {
  stage: string;
  progress: number;
}

export class EchoesApiClient {
  private baseUrl: string;
  private authToken: string | null;
  private defaultHeaders: Record<string, string>;

  constructor(baseUrl: string | null = null, authToken: string | null = null) {
    this.baseUrl = baseUrl || config.api.baseUrl;
    this.authToken = authToken;
    this.defaultHeaders = {
      'Content-Type': 'application/json',
    };
  }

  /**
   * Set authentication token
   */
  setAuthToken(token: string | null): void {
    this.authToken = token;
  }

  /**
   * Get request headers with authentication
   */
  getHeaders(additionalHeaders: Record<string, string> = {}): Record<string, string> {
    const headers = { ...this.defaultHeaders, ...additionalHeaders };
    
    if (this.authToken) {
      headers['Authorization'] = `Bearer ${this.authToken}`;
    }
    
    return headers;
  }

  /**
   * Make HTTP request
   */
  async request(endpoint: string, options: ApiClientOptions = {}): Promise<any> {
    const url = getApiUrl(endpoint);
    const requestConfig = {
      headers: this.getHeaders(options.headers),
      ...options,
    };

    try {
      const response = await fetch(url, requestConfig);
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new ApiError(
          errorData.detail || 'Request failed',
          response.status,
          errorData
        );
      }

      // Handle empty responses
      if (response.status === 204) {
        return null;
      }

      return await response.json();
    } catch (error) {
      if (error instanceof ApiError) {
        throw error;
      }
      
      console.error('API request failed:', error);
      throw new ApiError('Network error', 0, { originalError: error });
    }
  }

  /**
   * GET request
   */
  async get(endpoint: string, params: Record<string, any> = {}): Promise<any> {
    const queryString = new URLSearchParams(params).toString();
    const url = queryString ? `${endpoint}?${queryString}` : endpoint;
    
    return this.request(url, {
      method: 'GET',
    });
  }

  /**
   * POST request
   */
  async post(endpoint: string, data: any = null): Promise<any> {
    return this.request(endpoint, {
      method: 'POST',
      body: data ? JSON.stringify(data) : null,
    });
  }

  /**
   * PUT request
   */
  async put(endpoint: string, data: any = null): Promise<any> {
    return this.request(endpoint, {
      method: 'PUT',
      body: data ? JSON.stringify(data) : null,
    });
  }

  /**
   * DELETE request
   */
  async delete(endpoint: string): Promise<any> {
    return this.request(endpoint, {
      method: 'DELETE',
    });
  }

  /**
   * Upload file using FormData
   */
  async uploadFile(endpoint: string, formData: FormData): Promise<any> {
    return this.request(endpoint, {
      method: 'POST',
      headers: this.getHeaders({
        // Remove Content-Type to let browser set boundary for FormData
        'Content-Type': undefined,
      }),
      body: formData,
    });
  }

  // === Echo API Methods ===

  /**
   * Initialize audio upload
   */
  async initUpload(uploadData: UploadData): Promise<PresignedUrlResponse> {
    return this.post('/echoes/init-upload', uploadData);
  }

  /**
   * Upload audio directly to S3 using presigned URL
   */
  async uploadToS3(presignedData: PresignedUrlResponse, audioBlob: Blob): Promise<{ success: boolean; key: string }> {
    const formData = new FormData();
    
    // Add all required fields from presigned URL
    Object.entries(presignedData.fields).forEach(([key, value]) => {
      formData.append(key, value);
    });
    
    // Add the audio file
    formData.append('file', audioBlob);

    try {
      const response = await fetch(presignedData.upload_url, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`S3 upload failed: ${response.status} ${errorText}`);
      }

      return {
        success: true,
        key: presignedData.s3_key,
      };
    } catch (error) {
      console.error('S3 upload error:', error);
      throw error;
    }
  }

  /**
   * Create echo metadata after upload
   */
  async createEcho(echoData: EchoData): Promise<any> {
    return this.post('/echoes', echoData);
  }

  /**
   * Complete audio upload process
   */
  async uploadAudio(audioBlob: Blob, metadata: UploadMetadata): Promise<{ success: boolean; echo: any }> {
    try {
      // Step 1: Initialize upload
      const uploadData = {
        content_type: audioBlob.type || 'audio/webm',
        file_size: audioBlob.size,
        emotion: metadata.emotion,
        tags: metadata.tags || [],
        location: metadata.location,
      };

      const presignedResponse = await this.initUpload(uploadData);

      // Step 2: Upload to S3
      await this.uploadToS3(presignedResponse, audioBlob);

      // Step 3: Create echo metadata
      const echoData = {
        s3_key: presignedResponse.s3_key,
        emotion: metadata.emotion,
        tags: metadata.tags || [],
        location: metadata.location,
        transcript: metadata.transcript || '',
      };

      const echo = await this.createEcho(echoData);

      return {
        success: true,
        echo,
      };
    } catch (error) {
      console.error('Complete upload process failed:', error);
      throw error;
    }
  }

  /**
   * Get user's echoes
   */
  async getEchoes(filters: Record<string, any> = {}): Promise<any[]> {
    return this.get('/echoes', filters);
  }

  /**
   * Get a specific echo
   */
  async getEcho(echoId: string): Promise<any> {
    return this.get(`/echoes/${echoId}`);
  }

  /**
   * Get random echo by emotion
   */
  async getRandomEcho(emotion: string): Promise<any> {
    return this.get('/echoes/random', { emotion });
  }

  /**
   * Delete an echo
   */
  async deleteEcho(echoId: string): Promise<any> {
    return this.delete(`/echoes/${echoId}`);
  }

  /**
   * Get user statistics
   */
  async getUserStats(): Promise<any> {
    return this.get('/echoes/stats/user');
  }

  /**
   * Process uploaded file (alternative method)
   */
  async processUpload(audioFile: File): Promise<any> {
    const formData = new FormData();
    formData.append('file', audioFile);
    
    return this.uploadFile('/echoes/process-upload', formData);
  }

  // === Health Check ===

  /**
   * Check API health
   */
  async healthCheck(): Promise<any> {
    return this.get('/health');
  }
}

/**
 * Custom API Error class
 */
export class ApiError extends Error {
  statusCode: number;
  details: any;

  constructor(message: string, statusCode: number = 0, details: any = {}) {
    super(message);
    this.name = 'ApiError';
    this.statusCode = statusCode;
    this.details = details;
  }

  /**
   * Check if error is due to authentication
   */
  isAuthError(): boolean {
    return this.statusCode === 401;
  }

  /**
   * Check if error is due to forbidden access
   */
  isForbiddenError(): boolean {
    return this.statusCode === 403;
  }

  /**
   * Check if error is due to not found
   */
  isNotFoundError(): boolean {
    return this.statusCode === 404;
  }

  /**
   * Check if error is a validation error
   */
  isValidationError(): boolean {
    return this.statusCode === 422;
  }
}

/**
 * Audio upload utility with progress tracking
 */
export class AudioUploadManager {
  private apiClient: EchoesApiClient;
  private onProgress: ((event: ProgressEvent) => void) | null;
  private onComplete: ((echo: any) => void) | null;
  private onError: ((error: Error) => void) | null;

  constructor(apiClient: EchoesApiClient) {
    this.apiClient = apiClient;
    this.onProgress = null;
    this.onComplete = null;
    this.onError = null;
  }

  /**
   * Set event callbacks
   */
  setCallbacks({ onProgress, onComplete, onError }: {
    onProgress?: (event: ProgressEvent) => void;
    onComplete?: (echo: any) => void;
    onError?: (error: Error) => void;
  }): void {
    this.onProgress = onProgress || null;
    this.onComplete = onComplete || null;
    this.onError = onError || null;
  }

  /**
   * Upload audio with progress tracking
   */
  async uploadWithProgress(audioBlob: Blob, metadata: UploadMetadata): Promise<any> {
    try {
      if (this.onProgress) {
        this.onProgress({ stage: 'initializing', progress: 0 });
      }

      // Initialize upload
      const uploadData = {
        content_type: audioBlob.type || 'audio/webm',
        file_size: audioBlob.size,
        emotion: metadata.emotion,
        tags: metadata.tags || [],
        location: metadata.location,
      };

      if (this.onProgress) {
        this.onProgress({ stage: 'init-upload', progress: 20 });
      }

      const presignedResponse = await this.apiClient.initUpload(uploadData);

      if (this.onProgress) {
        this.onProgress({ stage: 'uploading', progress: 40 });
      }

      // Upload to S3 with XMLHttpRequest for progress tracking
      await this.uploadToS3WithProgress(presignedResponse, audioBlob);

      if (this.onProgress) {
        this.onProgress({ stage: 'creating-echo', progress: 80 });
      }

      // Create echo metadata
      const echoData = {
        s3_key: presignedResponse.s3_key,
        emotion: metadata.emotion,
        tags: metadata.tags || [],
        location: metadata.location,
        transcript: metadata.transcript || '',
      };

      const echo = await this.apiClient.createEcho(echoData);

      if (this.onProgress) {
        this.onProgress({ stage: 'complete', progress: 100 });
      }

      if (this.onComplete) {
        this.onComplete(echo);
      }

      return echo;
    } catch (error) {
      if (this.onError) {
        this.onError(error);
      }
      throw error;
    }
  }

  /**
   * Upload to S3 with progress tracking
   */
  uploadToS3WithProgress(presignedData: PresignedUrlResponse, audioBlob: Blob): Promise<void> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const formData = new FormData();

      // Add all required fields
      Object.entries(presignedData.fields).forEach(([key, value]) => {
        formData.append(key, value);
      });
      formData.append('file', audioBlob);

      // Track upload progress
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable && this.onProgress) {
          const uploadProgress = 40 + (event.loaded / event.total) * 40; // 40-80%
          this.onProgress({ stage: 'uploading', progress: uploadProgress });
        }
      };

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve();
        } else {
          reject(new Error(`S3 upload failed: ${xhr.status}`));
        }
      };

      xhr.onerror = () => {
        reject(new Error('S3 upload network error'));
      };

      xhr.open('POST', presignedData.upload_url);
      xhr.send(formData);
    });
  }
}

// Create default instance
export const apiClient = new EchoesApiClient();

export default EchoesApiClient;