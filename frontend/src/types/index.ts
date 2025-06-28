export interface Location {
  lat: number;
  lng: number;
  address?: string;
}

export interface Echo {
  echoId: string;
  userId: string;
  emotion: string;
  timestamp: string;
  s3Url: string;
  location?: Location;
  tags?: string[];
  transcript?: string;
  detectedMood?: string;
  duration: number;
}

export interface User {
  userId: string;
  email: string;
  name: string;
  createdAt: string;
}

export interface RecordingState {
  isRecording: boolean;
  duration: number;
  audioBlob?: Blob;
  audioUrl?: string;
}

export interface EmotionTag {
  id: string;
  label: string;
  color: string;
  emoji: string;
}

export interface EchoCreate {
  userId: string;
  emotion: string;
  s3Url: string;
  location?: Location;
  tags?: string[];
  duration: number;
  transcript?: string;
}

export interface PresignedUrlRequest {
  content_type: string;
  file_size: number;
  emotion: string;
  tags?: string[];
  location?: Location;
}

export const EMOTION_TAGS: EmotionTag[] = [
  { id: 'joy', label: 'Joy', color: 'yellow', emoji: '😊' },
  { id: 'calm', label: 'Calm', color: 'blue', emoji: '😌' },
  { id: 'excited', label: 'Excited', color: 'orange', emoji: '🤩' },
  { id: 'nostalgic', label: 'Nostalgic', color: 'purple', emoji: '🥺' },
  { id: 'peaceful', label: 'Peaceful', color: 'green', emoji: '☮️' },
  { id: 'grateful', label: 'Grateful', color: 'pink', emoji: '🙏' },
  { id: 'curious', label: 'Curious', color: 'indigo', emoji: '🤔' },
  { id: 'content', label: 'Content', color: 'teal', emoji: '😌' },
  { id: 'playful', label: 'Playful', color: 'lime', emoji: '😄' },
  { id: 'reflective', label: 'Reflective', color: 'slate', emoji: '🤨' },
];