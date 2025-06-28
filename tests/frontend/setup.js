/**
 * Jest setup for React component testing
 * Configures testing environment for Echoes frontend components
 */

import '@testing-library/jest-dom';
import 'whatwg-fetch';

// Mock Audio API
global.Audio = jest.fn().mockImplementation(() => ({
  play: jest.fn().mockResolvedValue(undefined),
  pause: jest.fn(),
  load: jest.fn(),
  addEventListener: jest.fn(),
  removeEventListener: jest.fn(),
  currentTime: 0,
  duration: 30,
  paused: true,
  volume: 1,
}));

// Mock MediaRecorder API
global.MediaRecorder = jest.fn().mockImplementation(() => ({
  start: jest.fn(),
  stop: jest.fn(),
  pause: jest.fn(),
  resume: jest.fn(),
  addEventListener: jest.fn(),
  removeEventListener: jest.fn(),
  state: 'inactive',
  stream: null,
}));

// Mock navigator.mediaDevices
Object.defineProperty(navigator, 'mediaDevices', {
  writable: true,
  value: {
    getUserMedia: jest.fn().mockResolvedValue({
      getTracks: () => [{ stop: jest.fn() }],
    }),
  },
});

// Mock geolocation
Object.defineProperty(navigator, 'geolocation', {
  writable: true,
  value: {
    getCurrentPosition: jest.fn().mockImplementation((success) => {
      success({
        coords: {
          latitude: 37.5407,
          longitude: -77.4360,
        },
      });
    }),
    watchPosition: jest.fn(),
    clearWatch: jest.fn(),
  },
});

// Mock localStorage
const localStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
};
global.localStorage = localStorageMock;

// Mock sessionStorage
const sessionStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
};
global.sessionStorage = sessionStorageMock;

// Mock fetch
global.fetch = jest.fn();

// Mock URL.createObjectURL
global.URL.createObjectURL = jest.fn(() => 'mocked-url');
global.URL.revokeObjectURL = jest.fn();

// Mock ResizeObserver
global.ResizeObserver = jest.fn().mockImplementation(() => ({
  observe: jest.fn(),
  unobserve: jest.fn(),
  disconnect: jest.fn(),
}));

// Mock IntersectionObserver
global.IntersectionObserver = jest.fn().mockImplementation(() => ({
  observe: jest.fn(),
  unobserve: jest.fn(),
  disconnect: jest.fn(),
}));

// Global test utilities
global.createMockEcho = (overrides = {}) => ({
  echoId: 'test-echo-123',
  userId: 'test-user-456',
  emotion: 'joy',
  timestamp: '2025-06-25T15:00:00Z',
  s3Url: 'https://test-bucket.s3.amazonaws.com/test-audio.wav',
  location: {
    lat: 37.5407,
    lng: -77.4360,
  },
  tags: ['test', 'sample'],
  transcript: 'Test audio transcript',
  detectedMood: 'happy',
  ...overrides,
});

global.createMockUser = (overrides = {}) => ({
  userId: 'test-user-456',
  email: 'test@example.com',
  accessToken: 'mock-access-token',
  idToken: 'mock-id-token',
  refreshToken: 'mock-refresh-token',
  ...overrides,
});