# 🌐 Frontend Integration Guide

Complete integration examples for connecting frontend applications to the Echoes Audio Time Machine API.

## Table of Contents

- [Authentication Setup](#authentication-setup)
- [JavaScript/TypeScript SDK](#javascripttypescript-sdk)
- [React Integration](#react-integration)
- [Vue.js Integration](#vuejs-integration)
- [Angular Integration](#angular-integration)
- [React Native Integration](#react-native-integration)
- [WebRTC Audio Recording](#webrtc-audio-recording)
- [File Upload Patterns](#file-upload-patterns)
- [Error Handling](#error-handling)
- [State Management](#state-management)

## Authentication Setup

### AWS Cognito Configuration

```javascript
// cognito-config.js
import { CognitoUserPool, CognitoUser, AuthenticationDetails } from 'amazon-cognito-identity-js';

const poolData = {
  UserPoolId: 'us-east-1_ABC123DEF',
  ClientId: 'your-client-id-here'
};

const userPool = new CognitoUserPool(poolData);

export class AuthService {
  async signIn(username, password) {
    return new Promise((resolve, reject) => {
      const authenticationDetails = new AuthenticationDetails({
        Username: username,
        Password: password,
      });

      const cognitoUser = new CognitoUser({
        Username: username,
        Pool: userPool,
      });

      cognitoUser.authenticateUser(authenticationDetails, {
        onSuccess: (result) => {
          const token = result.getAccessToken().getJwtToken();
          localStorage.setItem('echoes_jwt_token', token);
          resolve({ token, user: result });
        },
        onFailure: reject,
        newPasswordRequired: (userAttributes, requiredAttributes) => {
          // Handle new password requirement
          reject(new Error('New password required'));
        }
      });
    });
  }

  async signOut() {
    const cognitoUser = userPool.getCurrentUser();
    if (cognitoUser) {
      cognitoUser.signOut();
    }
    localStorage.removeItem('echoes_jwt_token');
  }

  getToken() {
    return localStorage.getItem('echoes_jwt_token');
  }

  isAuthenticated() {
    const token = this.getToken();
    if (!token) return false;
    
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      return payload.exp * 1000 > Date.now();
    } catch {
      return false;
    }
  }
}
```

## JavaScript/TypeScript SDK

### Core API Client

```typescript
// echoes-api-client.ts
interface APIResponse<T> {
  data: T;
  status: number;
  headers: Record<string, string>;
}

interface EchoesAPIError {
  error: string;
  message: string;
  details?: Record<string, any>;
  timestamp: string;
}

export class EchoesAPIClient {
  private baseURL: string;
  private token: string | null = null;

  constructor(config: { baseURL: string }) {
    this.baseURL = config.baseURL;
  }

  setToken(token: string) {
    this.token = token;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<APIResponse<T>> {
    const url = `${this.baseURL}${endpoint}`;
    
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...options.headers as Record<string, string>,
    };

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    const response = await fetch(url, {
      ...options,
      headers,
    });

    const responseHeaders: Record<string, string> = {};
    response.headers.forEach((value, key) => {
      responseHeaders[key] = value;
    });

    if (!response.ok) {
      const errorData: EchoesAPIError = await response.json();
      throw new Error(`API Error: ${errorData.message}`);
    }

    const data = await response.json();
    return {
      data,
      status: response.status,
      headers: responseHeaders,
    };
  }

  // Echo Management
  async initUpload(request: PresignedUrlRequest): Promise<PresignedUrlResponse> {
    const response = await this.request<PresignedUrlResponse>('/api/v1/echoes/init-upload', {
      method: 'POST',
      body: JSON.stringify(request),
    });
    return response.data;
  }

  async uploadToS3(uploadUrl: string, file: File): Promise<void> {
    const response = await fetch(uploadUrl, {
      method: 'PUT',
      body: file,
      headers: {
        'Content-Type': file.type,
      },
    });

    if (!response.ok) {
      throw new Error(`S3 Upload failed: ${response.statusText}`);
    }
  }

  async createEcho(echoId: string, data: EchoCreateRequest): Promise<EchoResponse> {
    const response = await this.request<EchoResponse>(`/api/v1/echoes?echo_id=${echoId}`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
    return response.data;
  }

  async listEchoes(params: {
    emotion?: string;
    page?: number;
    pageSize?: number;
  } = {}): Promise<EchoListResponse> {
    const queryParams = new URLSearchParams();
    if (params.emotion) queryParams.append('emotion', params.emotion);
    if (params.page) queryParams.append('page', params.page.toString());
    if (params.pageSize) queryParams.append('page_size', params.pageSize.toString());

    const response = await this.request<EchoListResponse>(`/api/v1/echoes?${queryParams}`);
    return response.data;
  }

  async getRandomEcho(emotion?: string): Promise<EchoResponse> {
    const queryParams = emotion ? `?emotion=${emotion}` : '';
    const response = await this.request<EchoResponse>(`/api/v1/echoes/random${queryParams}`);
    return response.data;
  }

  async getEcho(echoId: string): Promise<EchoResponse> {
    const response = await this.request<EchoResponse>(`/api/v1/echoes/${echoId}`);
    return response.data;
  }

  async deleteEcho(echoId: string): Promise<void> {
    await this.request(`/api/v1/echoes/${echoId}`, {
      method: 'DELETE',
    });
  }

  // System endpoints
  async healthCheck(): Promise<HealthResponse> {
    const response = await this.request<HealthResponse>('/health');
    return response.data;
  }
}

// Type definitions
interface PresignedUrlRequest {
  file_extension: string;
  content_type: string;
}

interface PresignedUrlResponse {
  upload_url: string;
  echo_id: string;
  s3_key: string;
  expires_in: number;
}

interface EchoCreateRequest {
  emotion: string;
  tags: string[];
  transcript?: string;
  detected_mood?: string;
  file_extension: string;
  duration_seconds?: number;
  location?: {
    lat: number;
    lng: number;
    address?: string;
  };
}

interface EchoResponse {
  echo_id: string;
  emotion: string;
  timestamp: string;
  s3_url: string;
  location?: {
    lat: number;
    lng: number;
    address?: string;
  };
  tags: string[];
  transcript?: string;
  detected_mood?: string;
  duration_seconds?: number;
  created_at: string;
}

interface EchoListResponse {
  echoes: EchoResponse[];
  total_count: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

interface HealthResponse {
  status: string;
  service: string;
  version: string;
  environment: string;
  dependencies?: Record<string, string>;
  timestamp: string;
}
```

## React Integration

### Custom Hooks

```typescript
// hooks/useEchoesAPI.ts
import { useState, useEffect, useCallback } from 'react';
import { EchoesAPIClient } from '../services/echoes-api-client';

const apiClient = new EchoesAPIClient({
  baseURL: process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000'
});

export function useAuth() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('echoes_jwt_token');
    if (token) {
      apiClient.setToken(token);
      setIsAuthenticated(true);
    }
    setLoading(false);
  }, []);

  const login = useCallback(async (token: string) => {
    localStorage.setItem('echoes_jwt_token', token);
    apiClient.setToken(token);
    setIsAuthenticated(true);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('echoes_jwt_token');
    apiClient.setToken('');
    setIsAuthenticated(false);
  }, []);

  return { isAuthenticated, loading, login, logout };
}

export function useEchoes(filters: { emotion?: string; pageSize?: number } = {}) {
  const [echoes, setEchoes] = useState<EchoResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [page, setPage] = useState(1);

  const fetchEchoes = useCallback(async (reset = false) => {
    setLoading(true);
    setError(null);

    try {
      const currentPage = reset ? 1 : page;
      const response = await apiClient.listEchoes({
        emotion: filters.emotion,
        page: currentPage,
        pageSize: filters.pageSize || 20,
      });

      if (reset) {
        setEchoes(response.echoes);
        setPage(2);
      } else {
        setEchoes(prev => [...prev, ...response.echoes]);
        setPage(prev => prev + 1);
      }

      setHasMore(response.has_more);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [filters.emotion, filters.pageSize, page]);

  const refresh = useCallback(() => {
    setPage(1);
    fetchEchoes(true);
  }, [fetchEchoes]);

  const loadMore = useCallback(() => {
    if (!loading && hasMore) {
      fetchEchoes(false);
    }
  }, [fetchEchoes, loading, hasMore]);

  useEffect(() => {
    fetchEchoes(true);
  }, [filters.emotion, filters.pageSize]);

  return {
    echoes,
    loading,
    error,
    hasMore,
    refresh,
    loadMore,
  };
}

export function useEchoUpload() {
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const upload = useCallback(async (params: {
    file: File;
    emotion: string;
    tags: string[];
    transcript?: string;
    location?: { lat: number; lng: number; address?: string };
  }) => {
    setUploading(true);
    setProgress(0);
    setError(null);

    try {
      // Step 1: Initialize upload
      setProgress(0.1);
      const fileExtension = params.file.name.split('.').pop()?.toLowerCase();
      const initResponse = await apiClient.initUpload({
        file_extension: fileExtension!,
        content_type: params.file.type,
      });

      // Step 2: Upload to S3
      setProgress(0.3);
      await apiClient.uploadToS3(initResponse.upload_url, params.file);

      // Step 3: Create echo metadata
      setProgress(0.8);
      const echo = await apiClient.createEcho(initResponse.echo_id, {
        emotion: params.emotion,
        tags: params.tags,
        transcript: params.transcript,
        file_extension: fileExtension!,
        duration_seconds: await getAudioDuration(params.file),
        location: params.location,
      });

      setProgress(1);
      return echo;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
      throw err;
    } finally {
      setUploading(false);
    }
  }, []);

  const reset = useCallback(() => {
    setUploading(false);
    setProgress(0);
    setError(null);
  }, []);

  return { upload, uploading, progress, error, reset };
}

// Utility function to get audio duration
async function getAudioDuration(file: File): Promise<number> {
  return new Promise((resolve) => {
    const audio = new Audio();
    audio.addEventListener('loadedmetadata', () => {
      resolve(audio.duration);
    });
    audio.src = URL.createObjectURL(file);
  });
}
```

### React Components

```tsx
// components/EchoRecorder.tsx
import React, { useState, useRef } from 'react';
import { useEchoUpload } from '../hooks/useEchoesAPI';

export const EchoRecorder: React.FC = () => {
  const [isRecording, setIsRecording] = useState(false);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [emotion, setEmotion] = useState('calm');
  const [tags, setTags] = useState<string[]>([]);
  const [transcript, setTranscript] = useState('');
  
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  
  const { upload, uploading, progress, error } = useEchoUpload();

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
        setAudioBlob(blob);
        
        // Stop all tracks to release microphone
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorder.start();
      setIsRecording(true);
    } catch (err) {
      console.error('Error accessing microphone:', err);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  const handleUpload = async () => {
    if (!audioBlob) return;

    try {
      const file = new File([audioBlob], 'recording.webm', { type: 'audio/webm' });
      await upload({
        file,
        emotion,
        tags,
        transcript: transcript || undefined,
      });
      
      // Reset form
      setAudioBlob(null);
      setTags([]);
      setTranscript('');
    } catch (err) {
      console.error('Upload failed:', err);
    }
  };

  const emotions = [
    'joy', 'calm', 'sadness', 'anger', 'fear', 'surprise',
    'love', 'nostalgia', 'excitement', 'peaceful', 'melancholy', 'hope'
  ];

  return (
    <div className="echo-recorder">
      <div className="recording-controls">
        {!isRecording && !audioBlob && (
          <button onClick={startRecording} className="record-btn">
            🎤 Start Recording
          </button>
        )}
        
        {isRecording && (
          <button onClick={stopRecording} className="stop-btn">
            ⏹️ Stop Recording
          </button>
        )}
        
        {audioBlob && (
          <div className="recorded-audio">
            <audio controls src={URL.createObjectURL(audioBlob)} />
            <button onClick={() => setAudioBlob(null)}>🗑️ Delete</button>
          </div>
        )}
      </div>

      {audioBlob && (
        <div className="echo-metadata">
          <div className="form-group">
            <label>Emotion:</label>
            <select value={emotion} onChange={(e) => setEmotion(e.target.value)}>
              {emotions.map(em => (
                <option key={em} value={em}>{em}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label>Tags (comma-separated):</label>
            <input
              type="text"
              value={tags.join(', ')}
              onChange={(e) => setTags(e.target.value.split(',').map(t => t.trim()))}
              placeholder="outdoor, family, nature"
            />
          </div>

          <div className="form-group">
            <label>Description:</label>
            <textarea
              value={transcript}
              onChange={(e) => setTranscript(e.target.value)}
              placeholder="Describe what's happening in this recording..."
            />
          </div>

          <button 
            onClick={handleUpload} 
            disabled={uploading}
            className="upload-btn"
          >
            {uploading ? `Uploading... ${Math.round(progress * 100)}%` : 'Save Echo'}
          </button>

          {error && <div className="error">Error: {error}</div>}
        </div>
      )}
    </div>
  );
};
```

```tsx
// components/EchosList.tsx
import React from 'react';
import { useEchoes } from '../hooks/useEchoesAPI';

interface EchosListProps {
  emotion?: string;
}

export const EchosList: React.FC<EchosListProps> = ({ emotion }) => {
  const { echoes, loading, error, hasMore, loadMore } = useEchoes({ emotion });

  if (loading && echoes.length === 0) {
    return <div className="loading">Loading echoes...</div>;
  }

  if (error) {
    return <div className="error">Error: {error}</div>;
  }

  return (
    <div className="echoes-list">
      <div className="echoes-grid">
        {echoes.map((echo) => (
          <EchoCard key={echo.echo_id} echo={echo} />
        ))}
      </div>
      
      {hasMore && (
        <button 
          onClick={loadMore} 
          disabled={loading}
          className="load-more-btn"
        >
          {loading ? 'Loading...' : 'Load More'}
        </button>
      )}
    </div>
  );
};

interface EchoCardProps {
  echo: EchoResponse;
}

const EchoCard: React.FC<EchoCardProps> = ({ echo }) => {
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString();
  };

  return (
    <div className="echo-card">
      <div className="echo-header">
        <span className="emotion-badge">{echo.emotion}</span>
        <span className="date">{formatDate(echo.created_at)}</span>
      </div>
      
      <div className="echo-content">
        {echo.transcript && (
          <p className="transcript">{echo.transcript}</p>
        )}
        
        {echo.tags.length > 0 && (
          <div className="tags">
            {echo.tags.map((tag, index) => (
              <span key={index} className="tag">#{tag}</span>
            ))}
          </div>
        )}
        
        {echo.location && (
          <div className="location">
            📍 {echo.location.address || `${echo.location.lat}, ${echo.location.lng}`}
          </div>
        )}
      </div>
      
      <div className="echo-actions">
        <button className="play-btn">▶️ Play</button>
        <button className="share-btn">🔗 Share</button>
      </div>
    </div>
  );
};
```

## Vue.js Integration

### Vue Composables

```typescript
// composables/useEchoes.ts
import { ref, computed, reactive } from 'vue';
import { EchoesAPIClient } from '../services/echoes-api-client';

const apiClient = new EchoesAPIClient({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
});

export function useEchoesAPI() {
  const echoes = ref<EchoResponse[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);

  const fetchEchoes = async (filters: { emotion?: string; page?: number } = {}) => {
    loading.value = true;
    error.value = null;

    try {
      const response = await apiClient.listEchoes(filters);
      echoes.value = response.echoes;
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error';
    } finally {
      loading.value = false;
    }
  };

  const uploadEcho = async (params: {
    file: File;
    emotion: string;
    tags: string[];
    transcript?: string;
  }) => {
    loading.value = true;
    error.value = null;

    try {
      const fileExtension = params.file.name.split('.').pop()?.toLowerCase();
      
      // Initialize upload
      const initResponse = await apiClient.initUpload({
        file_extension: fileExtension!,
        content_type: params.file.type,
      });

      // Upload to S3
      await apiClient.uploadToS3(initResponse.upload_url, params.file);

      // Create echo metadata
      const echo = await apiClient.createEcho(initResponse.echo_id, {
        emotion: params.emotion,
        tags: params.tags,
        transcript: params.transcript,
        file_extension: fileExtension!,
      });

      // Add to local list
      echoes.value.unshift(echo);
      return echo;
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Upload failed';
      throw err;
    } finally {
      loading.value = false;
    }
  };

  const deleteEcho = async (echoId: string) => {
    try {
      await apiClient.deleteEcho(echoId);
      echoes.value = echoes.value.filter(echo => echo.echo_id !== echoId);
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Delete failed';
      throw err;
    }
  };

  return {
    echoes: computed(() => echoes.value),
    loading: computed(() => loading.value),
    error: computed(() => error.value),
    fetchEchoes,
    uploadEcho,
    deleteEcho,
  };
}
```

### Vue Component

```vue
<!-- components/EchoManager.vue -->
<template>
  <div class="echo-manager">
    <div class="upload-section">
      <h2>Record New Echo</h2>
      <div class="recorder">
        <button 
          v-if="!isRecording && !audioBlob" 
          @click="startRecording"
          class="record-btn"
        >
          🎤 Start Recording
        </button>
        
        <button 
          v-if="isRecording" 
          @click="stopRecording"
          class="stop-btn"
        >
          ⏹️ Stop Recording
        </button>
        
        <div v-if="audioBlob" class="recorded-audio">
          <audio :src="audioUrl" controls></audio>
          <button @click="clearRecording">🗑️ Delete</button>
        </div>
      </div>

      <form v-if="audioBlob" @submit.prevent="handleUpload" class="metadata-form">
        <div class="form-group">
          <label>Emotion:</label>
          <select v-model="uploadForm.emotion">
            <option v-for="emotion in emotions" :key="emotion" :value="emotion">
              {{ emotion }}
            </option>
          </select>
        </div>

        <div class="form-group">
          <label>Tags:</label>
          <input 
            v-model="tagsInput" 
            type="text" 
            placeholder="outdoor, family, nature"
          />
        </div>

        <div class="form-group">
          <label>Description:</label>
          <textarea 
            v-model="uploadForm.transcript"
            placeholder="Describe what's happening..."
          ></textarea>
        </div>

        <button type="submit" :disabled="loading" class="upload-btn">
          {{ loading ? 'Uploading...' : 'Save Echo' }}
        </button>
      </form>
    </div>

    <div class="echoes-section">
      <h2>Your Echoes</h2>
      <div class="filters">
        <select v-model="selectedEmotion" @change="filterEchoes">
          <option value="">All Emotions</option>
          <option v-for="emotion in emotions" :key="emotion" :value="emotion">
            {{ emotion }}
          </option>
        </select>
      </div>

      <div v-if="loading" class="loading">Loading...</div>
      <div v-if="error" class="error">{{ error }}</div>

      <div class="echoes-grid">
        <div 
          v-for="echo in echoes" 
          :key="echo.echo_id" 
          class="echo-card"
        >
          <div class="echo-header">
            <span class="emotion">{{ echo.emotion }}</span>
            <span class="date">{{ formatDate(echo.created_at) }}</span>
          </div>
          
          <div class="echo-content">
            <p v-if="echo.transcript">{{ echo.transcript }}</p>
            <div v-if="echo.tags.length" class="tags">
              <span v-for="tag in echo.tags" :key="tag" class="tag">
                #{{ tag }}
              </span>
            </div>
          </div>
          
          <div class="echo-actions">
            <button @click="playEcho(echo)">▶️ Play</button>
            <button @click="deleteEcho(echo.echo_id)">🗑️ Delete</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useEchoesAPI } from '../composables/useEchoes';

const { echoes, loading, error, fetchEchoes, uploadEcho, deleteEcho } = useEchoesAPI();

const isRecording = ref(false);
const audioBlob = ref<Blob | null>(null);
const mediaRecorder = ref<MediaRecorder | null>(null);
const selectedEmotion = ref('');

const uploadForm = reactive({
  emotion: 'calm',
  transcript: '',
});

const tagsInput = ref('');

const emotions = [
  'joy', 'calm', 'sadness', 'anger', 'fear', 'surprise',
  'love', 'nostalgia', 'excitement', 'peaceful', 'melancholy', 'hope'
];

const audioUrl = computed(() => 
  audioBlob.value ? URL.createObjectURL(audioBlob.value) : ''
);

const startRecording = async () => {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder.value = new MediaRecorder(stream);
    
    const chunks: Blob[] = [];
    
    mediaRecorder.value.ondataavailable = (event) => {
      chunks.push(event.data);
    };
    
    mediaRecorder.value.onstop = () => {
      audioBlob.value = new Blob(chunks, { type: 'audio/webm' });
      stream.getTracks().forEach(track => track.stop());
    };
    
    mediaRecorder.value.start();
    isRecording.value = true;
  } catch (err) {
    console.error('Error accessing microphone:', err);
  }
};

const stopRecording = () => {
  if (mediaRecorder.value) {
    mediaRecorder.value.stop();
    isRecording.value = false;
  }
};

const clearRecording = () => {
  audioBlob.value = null;
  uploadForm.transcript = '';
  tagsInput.value = '';
};

const handleUpload = async () => {
  if (!audioBlob.value) return;
  
  try {
    const file = new File([audioBlob.value], 'recording.webm', { type: 'audio/webm' });
    const tags = tagsInput.value.split(',').map(t => t.trim()).filter(Boolean);
    
    await uploadEcho({
      file,
      emotion: uploadForm.emotion,
      tags,
      transcript: uploadForm.transcript || undefined,
    });
    
    clearRecording();
  } catch (err) {
    console.error('Upload failed:', err);
  }
};

const filterEchoes = () => {
  fetchEchoes({ emotion: selectedEmotion.value || undefined });
};

const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleDateString();
};

const playEcho = (echo: EchoResponse) => {
  // Implement audio playback
  console.log('Playing echo:', echo);
};

onMounted(() => {
  fetchEchoes();
});
</script>
```

## Angular Integration

### Angular Service

```typescript
// services/echoes-api.service.ts
import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { Observable, BehaviorSubject } from 'rxjs';
import { environment } from '../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class EchoesApiService {
  private baseURL = environment.apiBaseUrl;
  private tokenSubject = new BehaviorSubject<string | null>(null);
  
  constructor(private http: HttpClient) {
    const token = localStorage.getItem('echoes_jwt_token');
    if (token) {
      this.tokenSubject.next(token);
    }
  }

  private getHeaders(): HttpHeaders {
    const token = this.tokenSubject.value;
    let headers = new HttpHeaders({
      'Content-Type': 'application/json'
    });
    
    if (token) {
      headers = headers.set('Authorization', `Bearer ${token}`);
    }
    
    return headers;
  }

  setToken(token: string): void {
    localStorage.setItem('echoes_jwt_token', token);
    this.tokenSubject.next(token);
  }

  clearToken(): void {
    localStorage.removeItem('echoes_jwt_token');
    this.tokenSubject.next(null);
  }

  // Echo operations
  initUpload(request: PresignedUrlRequest): Observable<PresignedUrlResponse> {
    return this.http.post<PresignedUrlResponse>(
      `${this.baseURL}/api/v1/echoes/init-upload`,
      request,
      { headers: this.getHeaders() }
    );
  }

  uploadToS3(uploadUrl: string, file: File): Observable<any> {
    return this.http.put(uploadUrl, file, {
      headers: new HttpHeaders({
        'Content-Type': file.type
      })
    });
  }

  createEcho(echoId: string, data: EchoCreateRequest): Observable<EchoResponse> {
    const params = new HttpParams().set('echo_id', echoId);
    return this.http.post<EchoResponse>(
      `${this.baseURL}/api/v1/echoes`,
      data,
      { headers: this.getHeaders(), params }
    );
  }

  listEchoes(filters: {
    emotion?: string;
    page?: number;
    pageSize?: number;
  } = {}): Observable<EchoListResponse> {
    let params = new HttpParams();
    if (filters.emotion) params = params.set('emotion', filters.emotion);
    if (filters.page) params = params.set('page', filters.page.toString());
    if (filters.pageSize) params = params.set('page_size', filters.pageSize.toString());

    return this.http.get<EchoListResponse>(
      `${this.baseURL}/api/v1/echoes`,
      { headers: this.getHeaders(), params }
    );
  }

  getRandomEcho(emotion?: string): Observable<EchoResponse> {
    let params = new HttpParams();
    if (emotion) params = params.set('emotion', emotion);

    return this.http.get<EchoResponse>(
      `${this.baseURL}/api/v1/echoes/random`,
      { headers: this.getHeaders(), params }
    );
  }

  getEcho(echoId: string): Observable<EchoResponse> {
    return this.http.get<EchoResponse>(
      `${this.baseURL}/api/v1/echoes/${echoId}`,
      { headers: this.getHeaders() }
    );
  }

  deleteEcho(echoId: string): Observable<void> {
    return this.http.delete<void>(
      `${this.baseURL}/api/v1/echoes/${echoId}`,
      { headers: this.getHeaders() }
    );
  }

  healthCheck(): Observable<HealthResponse> {
    return this.http.get<HealthResponse>(`${this.baseURL}/health`);
  }
}
```

### Angular Component

```typescript
// components/echo-manager.component.ts
import { Component, OnInit, OnDestroy } from '@angular/core';
import { EchoesApiService } from '../services/echoes-api.service';
import { Subject, takeUntil } from 'rxjs';

@Component({
  selector: 'app-echo-manager',
  templateUrl: './echo-manager.component.html',
  styleUrls: ['./echo-manager.component.css']
})
export class EchoManagerComponent implements OnInit, OnDestroy {
  echoes: EchoResponse[] = [];
  loading = false;
  error: string | null = null;
  
  isRecording = false;
  audioBlob: Blob | null = null;
  audioUrl: string | null = null;
  
  uploadForm = {
    emotion: 'calm',
    tags: '',
    transcript: ''
  };
  
  selectedEmotion = '';
  
  emotions = [
    'joy', 'calm', 'sadness', 'anger', 'fear', 'surprise',
    'love', 'nostalgia', 'excitement', 'peaceful', 'melancholy', 'hope'
  ];
  
  private destroy$ = new Subject<void>();
  private mediaRecorder: MediaRecorder | null = null;

  constructor(private echoesApi: EchoesApiService) {}

  ngOnInit() {
    this.fetchEchoes();
  }

  ngOnDestroy() {
    this.destroy$.next();
    this.destroy$.complete();
    
    if (this.audioUrl) {
      URL.revokeObjectURL(this.audioUrl);
    }
  }

  fetchEchoes(emotion?: string) {
    this.loading = true;
    this.error = null;
    
    this.echoesApi.listEchoes({ emotion })
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (response) => {
          this.echoes = response.echoes;
          this.loading = false;
        },
        error: (err) => {
          this.error = err.message;
          this.loading = false;
        }
      });
  }

  async startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      this.mediaRecorder = new MediaRecorder(stream);
      
      const chunks: Blob[] = [];
      
      this.mediaRecorder.ondataavailable = (event) => {
        chunks.push(event.data);
      };
      
      this.mediaRecorder.onstop = () => {
        this.audioBlob = new Blob(chunks, { type: 'audio/webm' });
        this.audioUrl = URL.createObjectURL(this.audioBlob);
        stream.getTracks().forEach(track => track.stop());
      };
      
      this.mediaRecorder.start();
      this.isRecording = true;
    } catch (err) {
      console.error('Error accessing microphone:', err);
    }
  }

  stopRecording() {
    if (this.mediaRecorder) {
      this.mediaRecorder.stop();
      this.isRecording = false;
    }
  }

  clearRecording() {
    this.audioBlob = null;
    if (this.audioUrl) {
      URL.revokeObjectURL(this.audioUrl);
      this.audioUrl = null;
    }
    this.uploadForm = {
      emotion: 'calm',
      tags: '',
      transcript: ''
    };
  }

  uploadEcho() {
    if (!this.audioBlob) return;
    
    this.loading = true;
    const file = new File([this.audioBlob], 'recording.webm', { type: 'audio/webm' });
    const tags = this.uploadForm.tags.split(',').map(t => t.trim()).filter(Boolean);
    
    // Initialize upload
    this.echoesApi.initUpload({
      file_extension: 'webm',
      content_type: 'audio/webm'
    }).pipe(takeUntil(this.destroy$))
    .subscribe({
      next: (initResponse) => {
        // Upload to S3
        this.echoesApi.uploadToS3(initResponse.upload_url, file)
          .pipe(takeUntil(this.destroy$))
          .subscribe({
            next: () => {
              // Create echo metadata
              this.echoesApi.createEcho(initResponse.echo_id, {
                emotion: this.uploadForm.emotion,
                tags,
                transcript: this.uploadForm.transcript || undefined,
                file_extension: 'webm'
              }).pipe(takeUntil(this.destroy$))
              .subscribe({
                next: (echo) => {
                  this.echoes.unshift(echo);
                  this.clearRecording();
                  this.loading = false;
                },
                error: (err) => {
                  this.error = err.message;
                  this.loading = false;
                }
              });
            },
            error: (err) => {
              this.error = 'S3 upload failed';
              this.loading = false;
            }
          });
      },
      error: (err) => {
        this.error = err.message;
        this.loading = false;
      }
    });
  }

  deleteEcho(echoId: string) {
    this.echoesApi.deleteEcho(echoId)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: () => {
          this.echoes = this.echoes.filter(echo => echo.echo_id !== echoId);
        },
        error: (err) => {
          this.error = err.message;
        }
      });
  }

  onEmotionFilter() {
    this.fetchEchoes(this.selectedEmotion || undefined);
  }
}
```

## WebRTC Audio Recording

### Advanced Audio Recording Utility

```typescript
// utils/audio-recorder.ts
export class AudioRecorder {
  private mediaRecorder: MediaRecorder | null = null;
  private audioChunks: Blob[] = [];
  private stream: MediaStream | null = null;

  async initialize(options: {
    mimeType?: string;
    audioBitsPerSecond?: number;
    onDataAvailable?: (data: Blob) => void;
    onStop?: (audioBlob: Blob) => void;
  } = {}) {
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: 44100,
        }
      });

      const mimeType = this.getSupportedMimeType();
      
      this.mediaRecorder = new MediaRecorder(this.stream, {
        mimeType,
        audioBitsPerSecond: options.audioBitsPerSecond || 128000,
      });

      this.mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          this.audioChunks.push(event.data);
          options.onDataAvailable?.(event.data);
        }
      };

      this.mediaRecorder.onstop = () => {
        const audioBlob = new Blob(this.audioChunks, { type: mimeType });
        options.onStop?.(audioBlob);
        this.cleanup();
      };

    } catch (error) {
      throw new Error(`Failed to initialize audio recorder: ${error}`);
    }
  }

  start(timeslice?: number) {
    if (!this.mediaRecorder) {
      throw new Error('Recorder not initialized');
    }

    this.audioChunks = [];
    this.mediaRecorder.start(timeslice);
  }

  stop() {
    if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
      this.mediaRecorder.stop();
    }
  }

  pause() {
    if (this.mediaRecorder && this.mediaRecorder.state === 'recording') {
      this.mediaRecorder.pause();
    }
  }

  resume() {
    if (this.mediaRecorder && this.mediaRecorder.state === 'paused') {
      this.mediaRecorder.resume();
    }
  }

  private getSupportedMimeType(): string {
    const types = [
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/mp4',
      'audio/ogg;codecs=opus',
    ];

    for (const type of types) {
      if (MediaRecorder.isTypeSupported(type)) {
        return type;
      }
    }

    return 'audio/webm'; // Fallback
  }

  private cleanup() {
    if (this.stream) {
      this.stream.getTracks().forEach(track => track.stop());
      this.stream = null;
    }
  }

  get isRecording(): boolean {
    return this.mediaRecorder?.state === 'recording';
  }

  get isPaused(): boolean {
    return this.mediaRecorder?.state === 'paused';
  }

  get state(): string {
    return this.mediaRecorder?.state || 'inactive';
  }
}
```

## Error Handling

### Comprehensive Error Handler

```typescript
// utils/error-handler.ts
export interface APIError {
  error: string;
  message: string;
  details?: Record<string, any>;
  timestamp: string;
  status?: number;
}

export class EchoesAPIError extends Error {
  public readonly code: string;
  public readonly details?: Record<string, any>;
  public readonly timestamp: string;
  public readonly status?: number;

  constructor(apiError: APIError, status?: number) {
    super(apiError.message);
    this.name = 'EchoesAPIError';
    this.code = apiError.error;
    this.details = apiError.details;
    this.timestamp = apiError.timestamp;
    this.status = status;
  }

  get isAuthenticationError(): boolean {
    return this.code === 'authentication_failed' || this.status === 401;
  }

  get isValidationError(): boolean {
    return this.code === 'validation_error' || this.status === 400;
  }

  get isRateLimitError(): boolean {
    return this.code === 'rate_limit_exceeded' || this.status === 429;
  }

  get isServerError(): boolean {
    return this.status ? this.status >= 500 : false;
  }

  get retryAfter(): number | null {
    if (this.isRateLimitError && this.details?.retry_after) {
      return this.details.retry_after;
    }
    return null;
  }
}

export function handleAPIError(error: any): EchoesAPIError {
  if (error instanceof EchoesAPIError) {
    return error;
  }

  if (error.response?.data) {
    return new EchoesAPIError(error.response.data, error.response.status);
  }

  // Network or other errors
  return new EchoesAPIError({
    error: 'network_error',
    message: error.message || 'Network error occurred',
    timestamp: new Date().toISOString()
  });
}

// Error retry utility
export async function withRetry<T>(
  operation: () => Promise<T>,
  maxRetries = 3,
  delayMs = 1000
): Promise<T> {
  let lastError: Error;

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      return await operation();
    } catch (error) {
      lastError = handleAPIError(error);
      
      if (lastError.isRateLimitError && lastError.retryAfter) {
        // Wait for rate limit reset
        await new Promise(resolve => 
          setTimeout(resolve, lastError.retryAfter! * 1000)
        );
        continue;
      }

      if (attempt === maxRetries || !lastError.isServerError) {
        throw lastError;
      }

      // Exponential backoff for server errors
      await new Promise(resolve => 
        setTimeout(resolve, delayMs * Math.pow(2, attempt - 1))
      );
    }
  }

  throw lastError!;
}
```

This comprehensive frontend integration guide provides complete examples for:

1. **Authentication setup** with AWS Cognito
2. **TypeScript SDK** with full API coverage
3. **React hooks and components** for modern React apps
4. **Vue.js composables and components** for Vue applications
5. **Angular services and components** for Angular apps
6. **WebRTC audio recording** utilities
7. **Error handling** patterns and retry logic
8. **File upload patterns** with progress tracking

Each example includes proper TypeScript typing, error handling, and follows modern frontend development patterns. The code is production-ready and can be adapted to specific project needs.