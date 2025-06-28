import { type Echo } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

class EchoService {
  // This method will be used when connecting to the actual backend
  // @ts-ignore - Will be used when backend is connected
  private async request<T>(_endpoint: string, _options: RequestInit = {}): Promise<T> {
    const url = `${API_BASE_URL}${_endpoint}`;
    const token = localStorage.getItem('echoes_token');
    
    const response = await fetch(url, {
      ..._options,
      headers: {
        'Content-Type': 'application/json',
        ...(token && { Authorization: `Bearer ${token}` }),
        ..._options.headers,
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return response.json();
  }

  async getEchoes(emotion?: string): Promise<Echo[]> {
    // For now, return mock data until backend is ready
    return this.getMockEchoes(emotion);
  }

  async getRandomEcho(emotion?: string): Promise<Echo | null> {
    // For now, return mock data until backend is ready
    const echoes = this.getMockEchoes(emotion);
    return echoes.length > 0 ? echoes[Math.floor(Math.random() * echoes.length)] : null;
  }

  async saveEcho(echoData: Omit<Echo, 'echoId' | 'timestamp'>): Promise<Echo> {
    // For now, create a mock saved echo until backend is ready
    const echo: Echo = {
      ...echoData,
      echoId: `echo_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      timestamp: new Date().toISOString(),
    };

    // Store in localStorage for persistence during development
    const storedEchoes = JSON.parse(localStorage.getItem('echoes_mock_data') || '[]');
    storedEchoes.unshift(echo);
    localStorage.setItem('echoes_mock_data', JSON.stringify(storedEchoes));

    return echo;
  }

  async deleteEcho(echoId: string): Promise<void> {
    // Remove from localStorage for now
    const storedEchoes = JSON.parse(localStorage.getItem('echoes_mock_data') || '[]');
    const filteredEchoes = storedEchoes.filter((echo: Echo) => echo.echoId !== echoId);
    localStorage.setItem('echoes_mock_data', JSON.stringify(filteredEchoes));
  }

  async initUpload(): Promise<{ uploadUrl: string; echoId: string }> {
    // Mock implementation for now
    return {
      uploadUrl: `https://mock-s3-bucket.amazonaws.com/upload/${Date.now()}`,
      echoId: `echo_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
    };
  }

  private getMockEchoes(emotion?: string): Echo[] {
    // Get stored echoes from localStorage
    const storedEchoes = JSON.parse(localStorage.getItem('echoes_mock_data') || '[]');
    
    // Add some default mock echoes if none exist
    if (storedEchoes.length === 0) {
      const mockEchoes: Echo[] = [
        {
          echoId: 'echo_1',
          userId: 'user_1',
          emotion: 'Joy',
          timestamp: new Date(Date.now() - 86400000).toISOString(), // 1 day ago
          s3Url: 'https://mock-s3.amazonaws.com/echo_1.wav',
          location: { lat: 37.7749, lng: -122.4194, address: 'San Francisco, CA' },
          tags: ['morning', 'coffee', 'birds'],
          transcript: 'Birds chirping outside with morning coffee brewing',
          detectedMood: 'peaceful',
          duration: 15,
        },
        {
          echoId: 'echo_2',
          userId: 'user_1',
          emotion: 'Calm',
          timestamp: new Date(Date.now() - 172800000).toISOString(), // 2 days ago
          s3Url: 'https://mock-s3.amazonaws.com/echo_2.wav',
          location: { lat: 40.7128, lng: -74.0060, address: 'New York, NY' },
          tags: ['rain', 'window', 'reading'],
          transcript: 'Gentle rain against the window while reading',
          detectedMood: 'calm',
          duration: 22,
        },
        {
          echoId: 'echo_3',
          userId: 'user_1',
          emotion: 'Nostalgic',
          timestamp: new Date(Date.now() - 259200000).toISOString(), // 3 days ago
          s3Url: 'https://mock-s3.amazonaws.com/echo_3.wav',
          location: { lat: 34.0522, lng: -118.2437, address: 'Los Angeles, CA' },
          tags: ['childhood', 'laughter', 'playground'],
          transcript: 'Children playing and laughing at the old playground',
          detectedMood: 'nostalgic',
          duration: 18,
        },
      ];
      
      localStorage.setItem('echoes_mock_data', JSON.stringify(mockEchoes));
      storedEchoes.push(...mockEchoes);
    }

    // Filter by emotion if specified
    if (emotion) {
      return storedEchoes.filter((echo: Echo) => echo.emotion.toLowerCase() === emotion.toLowerCase());
    }

    return storedEchoes;
  }
}

export const echoService = new EchoService();