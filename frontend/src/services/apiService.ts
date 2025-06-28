/**
 * API Service
 * High-level API wrapper with error handling and response transformation
 */

import { apiClient, ApiError } from '../utils/apiClient';
import { config } from '../config';
import type { Echo, EchoCreate, PresignedUrlRequest } from '../types';

// Import interceptor to ensure it's initialized
import '../utils/apiInterceptor';

export interface ApiResponse<T> {
  data?: T;
  error?: string;
  success: boolean;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  hasMore: boolean;
}

class ApiService {
  /**
   * Generic error handler
   */
  private handleError(error: any): ApiResponse<any> {
    if (error instanceof ApiError) {
      return {
        success: false,
        error: error.message,
        data: error.details,
      };
    }
    
    return {
      success: false,
      error: error.message || 'An unexpected error occurred',
    };
  }

  /**
   * Health check
   */
  async checkHealth(): Promise<ApiResponse<any>> {
    try {
      const data = await apiClient.healthCheck();
      return { success: true, data };
    } catch (error) {
      return this.handleError(error);
    }
  }

  /**
   * Initialize echo upload
   */
  async initializeUpload(
    emotion: string,
    tags: string[] = [],
    location?: string
  ): Promise<ApiResponse<any>> {
    try {
      const request: PresignedUrlRequest = {
        content_type: 'audio/webm',
        file_size: 0, // Will be set by the recorder
        emotion,
        tags,
        location,
      };
      
      const data = await apiClient.initUpload(request);
      return { success: true, data };
    } catch (error) {
      return this.handleError(error);
    }
  }

  /**
   * Create echo after upload
   */
  async createEcho(
    echoId: string,
    echoData: EchoCreate
  ): Promise<ApiResponse<Echo>> {
    try {
      const data = await apiClient.post(`/echoes?echo_id=${echoId}`, echoData);
      return { success: true, data };
    } catch (error) {
      return this.handleError(error);
    }
  }

  /**
   * Get user's echoes with pagination
   */
  async getEchoes(
    page = 1,
    pageSize = 20,
    emotion?: string
  ): Promise<ApiResponse<PaginatedResponse<Echo>>> {
    try {
      const params: any = { page, page_size: pageSize };
      if (emotion) {
        params.emotion = emotion;
      }
      
      const response = await apiClient.getEchoes(params);
      
      const paginatedResponse: PaginatedResponse<Echo> = {
        items: response.echoes || [],
        total: response.total_count || 0,
        page: response.page || page,
        pageSize: response.page_size || pageSize,
        hasMore: response.has_more || false,
      };
      
      return { success: true, data: paginatedResponse };
    } catch (error) {
      return this.handleError(error);
    }
  }

  /**
   * Get specific echo
   */
  async getEcho(echoId: string): Promise<ApiResponse<Echo>> {
    try {
      const data = await apiClient.getEcho(echoId);
      return { success: true, data };
    } catch (error) {
      return this.handleError(error);
    }
  }

  /**
   * Get random echo
   */
  async getRandomEcho(emotion?: string): Promise<ApiResponse<Echo>> {
    try {
      const data = await apiClient.getRandomEcho(emotion);
      return { success: true, data };
    } catch (error) {
      return this.handleError(error);
    }
  }

  /**
   * Delete echo
   */
  async deleteEcho(echoId: string): Promise<ApiResponse<void>> {
    try {
      await apiClient.deleteEcho(echoId);
      return { success: true };
    } catch (error) {
      return this.handleError(error);
    }
  }

  /**
   * Upload audio with progress tracking
   */
  async uploadAudioWithProgress(
    audioBlob: Blob,
    metadata: {
      emotion: string;
      tags?: string[];
      location?: string;
      transcript?: string;
    },
    onProgress?: (progress: number) => void
  ): Promise<ApiResponse<Echo>> {
    try {
      // Step 1: Initialize upload (10% progress)
      onProgress?.(10);
      
      const initResponse = await this.initializeUpload(
        metadata.emotion,
        metadata.tags,
        metadata.location
      );
      
      if (!initResponse.success || !initResponse.data) {
        throw new Error(initResponse.error || 'Failed to initialize upload');
      }
      
      // Step 2: Upload to S3 (10-80% progress)
      onProgress?.(20);
      
      // Create a new XMLHttpRequest for progress tracking
      const uploadResult = await this.uploadToS3WithProgress(
        initResponse.data,
        audioBlob,
        (uploadProgress) => {
          // Map upload progress from 20% to 80%
          const mappedProgress = 20 + (uploadProgress * 0.6);
          onProgress?.(mappedProgress);
        }
      );
      
      if (!uploadResult.success) {
        throw new Error('Failed to upload audio to S3');
      }
      
      // Step 3: Create echo metadata (80-100% progress)
      onProgress?.(85);
      
      const echoData: EchoCreate = {
        file_extension: 'webm', // TODO: Extract from blob type
        emotion: metadata.emotion,
        tags: metadata.tags || [],
        transcript: metadata.transcript || '',
        location: metadata.location,
        duration_seconds: 0, // TODO: Calculate from audio
      };
      
      const echoResponse = await this.createEcho(
        initResponse.data.echo_id,
        echoData
      );
      
      onProgress?.(100);
      
      return echoResponse;
    } catch (error) {
      return this.handleError(error);
    }
  }

  /**
   * Upload to S3 with progress tracking
   */
  private uploadToS3WithProgress(
    presignedData: any,
    audioBlob: Blob,
    onProgress?: (progress: number) => void
  ): Promise<ApiResponse<void>> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const formData = new FormData();

      // Add all required fields
      if (presignedData.fields) {
        Object.entries(presignedData.fields).forEach(([key, value]) => {
          formData.append(key, String(value));
        });
      }
      formData.append('file', audioBlob);

      // Track upload progress
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) {
          const progress = (event.loaded / event.total) * 100;
          onProgress?.(progress);
        }
      };

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve({ success: true });
        } else {
          resolve({
            success: false,
            error: `S3 upload failed with status ${xhr.status}`,
          });
        }
      };

      xhr.onerror = () => {
        resolve({
          success: false,
          error: 'Network error during S3 upload',
        });
      };

      xhr.open('POST', presignedData.upload_url);
      xhr.send(formData);
    });
  }

  /**
   * Validate audio file before upload
   */
  validateAudioFile(file: File | Blob): { valid: boolean; error?: string } {
    // Check file size
    if (file.size > config.app.maxAudioFileSize) {
      return {
        valid: false,
        error: `File size exceeds maximum of ${config.app.maxAudioFileSize / 1024 / 1024}MB`,
      };
    }

    // Check file type
    if (file instanceof File) {
      const extension = file.name.split('.').pop()?.toLowerCase() || '';
      if (!config.app.allowedAudioFormats.includes(extension)) {
        return {
          valid: false,
          error: `File type not allowed. Allowed types: ${config.app.allowedAudioFormats.join(', ')}`,
        };
      }
    }

    return { valid: true };
  }
}

// Create and export singleton instance
export const apiService = new ApiService();

export default apiService;