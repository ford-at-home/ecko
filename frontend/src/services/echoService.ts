import { type Echo } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

class EchoService {
  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`;
    const token = localStorage.getItem('echoes_auth_token');
    
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token && { Authorization: `Bearer ${token}` }),
        ...options.headers,
      },
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('API Error:', response.status, errorText);
      
      // Try to parse error message from API
      let errorMessage = `API Error: ${response.status}`;
      try {
        const errorData = JSON.parse(errorText);
        errorMessage = errorData.detail || errorData.message || errorMessage;
      } catch {
        errorMessage = errorText || errorMessage;
      }
      
      throw new Error(errorMessage);
    }

    return response.json();
  }

  async getEchoes(emotion?: string): Promise<Echo[]> {
    const endpoint = emotion ? `/echoes?emotion=${encodeURIComponent(emotion)}` : '/echoes';
    return this.request<Echo[]>(endpoint);
  }

  async getRandomEcho(emotion?: string): Promise<Echo | null> {
    const endpoint = emotion ? `/echoes/random?emotion=${encodeURIComponent(emotion)}` : '/echoes/random';
    try {
      return await this.request<Echo>(endpoint);
    } catch (error) {
      console.error('Error getting random echo:', error);
      return null;
    }
  }

  async saveEcho(echoData: Omit<Echo, 'echoId' | 'timestamp'> & { audioBlob?: Blob }): Promise<Echo> {
    // First, get presigned URL for audio upload if audioBlob is provided
    let s3Url: string | undefined;
    
    if (echoData.audioBlob) {
      const { uploadUrl, echoId } = await this.initUpload();
      
      // Upload audio to S3 using presigned URL
      await fetch(uploadUrl, {
        method: 'PUT',
        body: echoData.audioBlob,
        headers: {
          'Content-Type': 'audio/webm',
        },
      });
      
      // Extract the S3 URL without query parameters
      s3Url = uploadUrl.split('?')[0];
      
      // Save echo metadata with the S3 URL
      const echoPayload = {
        emotion: echoData.emotion,
        tags: echoData.tags || [],
        transcript: echoData.transcript,
        file_extension: 'webm',
        duration_seconds: echoData.duration,
        location: echoData.location,
      };
      
      return this.request<Echo>(`/echoes?echo_id=${echoId}`, {
        method: 'POST',
        body: JSON.stringify(echoPayload),
      });
    }
    
    // If no audio blob, just save the echo metadata
    return this.request<Echo>('/echoes', {
      method: 'POST',
      body: JSON.stringify(echoData),
    });
  }

  async deleteEcho(echoId: string): Promise<void> {
    await this.request<void>(`/echoes/${echoId}`, {
      method: 'DELETE',
    });
  }

  async initUpload(): Promise<{ uploadUrl: string; echoId: string }> {
    return this.request<{ uploadUrl: string; echoId: string }>('/echoes/init-upload', {
      method: 'POST',
      body: JSON.stringify({ 
        file_extension: 'webm',
        content_type: 'audio/webm'
      }),
    });
  }

  // Health check method to verify API connectivity
  async healthCheck(): Promise<boolean> {
    try {
      await this.request<{ status: string }>('/health');
      return true;
    } catch (error) {
      console.error('API health check failed:', error);
      return false;
    }
  }
}

export const echoService = new EchoService();