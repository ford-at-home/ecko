/**
 * Audio Recorder React Component for Echoes App
 * Demonstrates integration of audio recording and upload functionality
 */

import React, { useState, useRef, useEffect } from 'react';
import { AudioRecorder, AudioVisualizer } from '../utils/audioRecorder';
import { AudioUploadManager, apiClient } from '../utils/apiClient';

const AudioRecorderComponent = ({ onEchoCreated, authToken }) => {
  // State management
  const [isRecording, setIsRecording] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [recordedBlob, setRecordedBlob] = useState(null);
  const [emotion, setEmotion] = useState('');
  const [tags, setTags] = useState('');
  const [error, setError] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(null);
  const [permissionGranted, setPermissionGranted] = useState(false);

  // Refs
  const recorderRef = useRef(null);
  const visualizerRef = useRef(null);
  const canvasRef = useRef(null);
  const audioPlayerRef = useRef(null);
  const uploadManagerRef = useRef(null);

  // Available emotions
  const emotions = [
    'Joy', 'Calm', 'Excited', 'Nostalgic', 'Peaceful',
    'Grateful', 'Inspired', 'Content', 'Hopeful', 'Reflective'
  ];

  // Initialize components
  useEffect(() => {
    // Set up API client authentication
    if (authToken) {
      apiClient.setAuthToken(authToken);
    }

    // Initialize upload manager
    uploadManagerRef.current = new AudioUploadManager(apiClient);
    uploadManagerRef.current.setCallbacks({
      onProgress: (progress) => {
        setUploadProgress(progress);
      },
      onComplete: (echo) => {
        setIsUploading(false);
        setUploadProgress(null);
        setRecordedBlob(null);
        setError(null);
        if (onEchoCreated) {
          onEchoCreated(echo);
        }
      },
      onError: (error) => {
        setIsUploading(false);
        setUploadProgress(null);
        setError(error.message);
      },
    });

    // Check browser support
    if (!AudioRecorder.isSupported()) {
      setError('Audio recording is not supported in this browser');
    }

    // Cleanup on unmount
    return () => {
      if (recorderRef.current) {
        recorderRef.current.cleanup();
      }
      if (visualizerRef.current) {
        visualizerRef.current.stop();
      }
    };
  }, [authToken, onEchoCreated]);

  // Request microphone permissions
  const requestPermissions = async () => {
    try {
      const granted = await AudioRecorder.requestPermissions();
      setPermissionGranted(granted);
      if (!granted) {
        setError('Microphone access is required to record audio');
      }
      return granted;
    } catch (error) {
      setError('Failed to request microphone permissions');
      return false;
    }
  };

  // Initialize recorder
  const initializeRecorder = async () => {
    try {
      if (!recorderRef.current) {
        recorderRef.current = new AudioRecorder();
      }

      // Set up recorder callbacks
      recorderRef.current.setCallbacks({
        onStop: (blob) => {
          setRecordedBlob(blob);
          setIsRecording(false);
          
          // Create audio URL for playback
          const audioUrl = URL.createObjectURL(blob);
          if (audioPlayerRef.current) {
            audioPlayerRef.current.src = audioUrl;
          }

          // Stop visualizer
          if (visualizerRef.current) {
            visualizerRef.current.stop();
          }
        },
        onError: (error) => {
          setError(error.message);
          setIsRecording(false);
        },
      });

      await recorderRef.current.initialize();

      // Initialize visualizer
      if (canvasRef.current && recorderRef.current.audioStream) {
        visualizerRef.current = new AudioVisualizer(canvasRef.current);
        await visualizerRef.current.initialize(recorderRef.current.audioStream);
      }

      return true;
    } catch (error) {
      setError('Failed to initialize audio recorder');
      return false;
    }
  };

  // Start recording
  const startRecording = async () => {
    try {
      setError(null);
      setRecordedBlob(null);

      // Check permissions
      if (!permissionGranted) {
        const granted = await requestPermissions();
        if (!granted) return;
      }

      // Initialize recorder if needed
      if (!recorderRef.current) {
        const initialized = await initializeRecorder();
        if (!initialized) return;
      }

      // Start recording
      await recorderRef.current.startRecording();
      setIsRecording(true);
    } catch (error) {
      setError('Failed to start recording: ' + error.message);
    }
  };

  // Stop recording
  const stopRecording = async () => {
    try {
      if (recorderRef.current && isRecording) {
        await recorderRef.current.stopRecording();
        
        // Check minimum duration
        if (!recorderRef.current.isMinimumDurationMet()) {
          setError('Recording must be at least 10 seconds long');
        }
      }
    } catch (error) {
      setError('Failed to stop recording: ' + error.message);
    }
  };

  // Upload recorded audio
  const uploadAudio = async () => {
    if (!recordedBlob || !emotion.trim()) {
      setError('Please record audio and select an emotion');
      return;
    }

    try {
      setIsUploading(true);
      setError(null);

      const metadata = {
        emotion: emotion.trim(),
        tags: tags.split(',').map(tag => tag.trim()).filter(tag => tag),
        location: null, // Could be added with geolocation
        transcript: '', // Could be added with speech recognition
      };

      await uploadManagerRef.current.uploadWithProgress(recordedBlob, metadata);
    } catch (error) {
      setError('Failed to upload audio: ' + error.message);
      setIsUploading(false);
      setUploadProgress(null);
    }
  };

  // Clear recorded audio
  const clearRecording = () => {
    setRecordedBlob(null);
    setError(null);
    if (audioPlayerRef.current) {
      audioPlayerRef.current.src = '';
    }
  };

  return (
    <div className="audio-recorder">
      <h2>Record Your Echo</h2>

      {/* Error display */}
      {error && (
        <div className="error-message" style={{ color: 'red', marginBottom: '1rem' }}>
          {error}
        </div>
      )}

      {/* Recording controls */}
      <div className="recording-controls" style={{ marginBottom: '1rem' }}>
        {!isRecording && !recordedBlob && (
          <button
            onClick={startRecording}
            disabled={isUploading}
            style={{
              padding: '1rem 2rem',
              fontSize: '1.2rem',
              backgroundColor: '#007bff',
              color: 'white',
              border: 'none',
              borderRadius: '8px',
              cursor: 'pointer',
            }}
          >
            🎤 Start Recording
          </button>
        )}

        {isRecording && (
          <button
            onClick={stopRecording}
            style={{
              padding: '1rem 2rem',
              fontSize: '1.2rem',
              backgroundColor: '#dc3545',
              color: 'white',
              border: 'none',
              borderRadius: '8px',
              cursor: 'pointer',
            }}
          >
            ⏹️ Stop Recording
          </button>
        )}
      </div>

      {/* Audio visualizer */}
      {isRecording && (
        <div className="visualizer" style={{ marginBottom: '1rem' }}>
          <canvas
            ref={canvasRef}
            width="400"
            height="100"
            style={{
              border: '1px solid #ccc',
              borderRadius: '4px',
              width: '100%',
              maxWidth: '400px',
            }}
          />
        </div>
      )}

      {/* Recording status */}
      {isRecording && (
        <div className="recording-status" style={{ marginBottom: '1rem', color: 'red' }}>
          🔴 Recording... (10-30 seconds)
        </div>
      )}

      {/* Audio playback */}
      {recordedBlob && !isUploading && (
        <div className="playback-section" style={{ marginBottom: '1rem' }}>
          <h3>Preview Your Recording</h3>
          <audio
            ref={audioPlayerRef}
            controls
            style={{ width: '100%', marginBottom: '1rem' }}
          />
          <button
            onClick={clearRecording}
            style={{
              padding: '0.5rem 1rem',
              backgroundColor: '#6c757d',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              marginRight: '0.5rem',
            }}
          >
            🗑️ Clear
          </button>
        </div>
      )}

      {/* Emotion and tags input */}
      {recordedBlob && !isUploading && (
        <div className="metadata-section" style={{ marginBottom: '1rem' }}>
          <h3>Describe Your Echo</h3>
          
          <div style={{ marginBottom: '1rem' }}>
            <label style={{ display: 'block', marginBottom: '0.5rem' }}>
              Emotion:
            </label>
            <select
              value={emotion}
              onChange={(e) => setEmotion(e.target.value)}
              style={{
                width: '100%',
                padding: '0.5rem',
                border: '1px solid #ccc',
                borderRadius: '4px',
              }}
            >
              <option value="">Select an emotion...</option>
              {emotions.map((em) => (
                <option key={em} value={em}>
                  {em}
                </option>
              ))}
            </select>
          </div>

          <div style={{ marginBottom: '1rem' }}>
            <label style={{ display: 'block', marginBottom: '0.5rem' }}>
              Tags (comma-separated):
            </label>
            <input
              type="text"
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              placeholder="nature, peaceful, morning..."
              style={{
                width: '100%',
                padding: '0.5rem',
                border: '1px solid #ccc',
                borderRadius: '4px',
              }}
            />
          </div>

          <button
            onClick={uploadAudio}
            disabled={!emotion.trim() || isUploading}
            style={{
              padding: '1rem 2rem',
              fontSize: '1.1rem',
              backgroundColor: emotion.trim() ? '#28a745' : '#6c757d',
              color: 'white',
              border: 'none',
              borderRadius: '8px',
              cursor: emotion.trim() ? 'pointer' : 'not-allowed',
              width: '100%',
            }}
          >
            💾 Save Echo
          </button>
        </div>
      )}

      {/* Upload progress */}
      {isUploading && uploadProgress && (
        <div className="upload-progress" style={{ marginBottom: '1rem' }}>
          <h3>Uploading Your Echo...</h3>
          <div
            style={{
              width: '100%',
              height: '20px',
              backgroundColor: '#e9ecef',
              borderRadius: '10px',
              overflow: 'hidden',
              marginBottom: '0.5rem',
            }}
          >
            <div
              style={{
                width: `${uploadProgress.progress}%`,
                height: '100%',
                backgroundColor: '#007bff',
                transition: 'width 0.3s ease',
              }}
            />
          </div>
          <div style={{ fontSize: '0.9rem', color: '#6c757d' }}>
            {uploadProgress.stage}: {Math.round(uploadProgress.progress)}%
          </div>
        </div>
      )}
    </div>
  );
};

export default AudioRecorderComponent;