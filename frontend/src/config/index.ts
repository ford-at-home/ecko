/**
 * Application configuration
 * Centralizes all environment variables and configuration settings
 */

// Helper to get environment variables with fallbacks
const getEnvVar = (key: string, defaultValue = ''): string => {
  return import.meta.env[key] || defaultValue;
};

const getBooleanEnvVar = (key: string, defaultValue = false): boolean => {
  const value = getEnvVar(key, String(defaultValue));
  return value === 'true' || value === '1';
};

const getNumberEnvVar = (key: string, defaultValue: number): number => {
  const value = getEnvVar(key, String(defaultValue));
  return parseInt(value, 10) || defaultValue;
};

export const config = {
  // API Configuration
  api: {
    baseUrl: getEnvVar('VITE_API_URL', 'http://localhost:8000'),
    prefix: getEnvVar('VITE_API_PREFIX', '/api/v1'),
    timeout: getNumberEnvVar('VITE_API_TIMEOUT', 30000), // 30 seconds
  },

  // AWS Cognito Configuration
  cognito: {
    userPoolId: getEnvVar('VITE_COGNITO_USER_POOL_ID'),
    clientId: getEnvVar('VITE_COGNITO_CLIENT_ID'),
    region: getEnvVar('VITE_COGNITO_REGION', 'us-east-1'),
  },

  // S3 Configuration
  s3: {
    bucketName: getEnvVar('VITE_S3_BUCKET_NAME', 'echoes-audio-dev'),
    region: getEnvVar('VITE_AWS_REGION', 'us-east-1'),
  },

  // Feature Flags
  features: {
    analytics: getBooleanEnvVar('VITE_ENABLE_ANALYTICS', false),
    debug: getBooleanEnvVar('VITE_ENABLE_DEBUG', true),
  },

  // App Configuration
  app: {
    name: getEnvVar('VITE_APP_NAME', 'Echoes Audio Time Machine'),
    maxAudioFileSize: getNumberEnvVar('VITE_MAX_AUDIO_FILE_SIZE', 10 * 1024 * 1024), // 10MB
    allowedAudioFormats: getEnvVar('VITE_ALLOWED_AUDIO_FORMATS', 'webm,wav,mp3,m4a,ogg')
      .split(',')
      .map(format => format.trim()),
  },

  // WebSocket Configuration
  ws: {
    url: getEnvVar('VITE_WS_URL', 'ws://localhost:8000'),
  },

  // Development/Production Detection
  isDevelopment: import.meta.env.DEV,
  isProduction: import.meta.env.PROD,
};

// Helper function to construct full API URL
export const getApiUrl = (endpoint: string): string => {
  // Remove leading slash if present
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  
  // In development, use relative URLs for proxy
  if (config.isDevelopment) {
    return `${config.api.prefix}${cleanEndpoint}`;
  }
  
  // In production, use full URL
  return `${config.api.baseUrl}${config.api.prefix}${cleanEndpoint}`;
};

// Helper to check if file type is allowed
export const isAllowedAudioFormat = (filename: string): boolean => {
  const extension = filename.split('.').pop()?.toLowerCase() || '';
  return config.app.allowedAudioFormats.includes(extension);
};

// Helper to check file size
export const isFileSizeValid = (sizeInBytes: number): boolean => {
  return sizeInBytes <= config.app.maxAudioFileSize;
};

// Export type for config
export type AppConfig = typeof config;

export default config;