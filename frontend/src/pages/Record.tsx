import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useEchoes } from '../contexts/EchoContext';
import { useAuth } from '../contexts/AuthContext';
import { type RecordingState, type Location } from '../types';

const Record: React.FC = () => {
  const navigate = useNavigate();
  const { saveEcho } = useEchoes();
  const { user } = useAuth();

  const [recordingState, setRecordingState] = useState<RecordingState>({
    isRecording: false,
    duration: 15, // Start at 15 seconds for countdown
  });
  
  const [emotionValue, setEmotionValue] = useState<number>(50); // 0 = sadness, 100 = joy
  const [caption, setCaption] = useState<string>('');
  const [location, setLocation] = useState<Location | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const intervalRef = useRef<number | null>(null);

  // Get user location
  useEffect(() => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          setLocation({
            lat: position.coords.latitude,
            lng: position.coords.longitude,
            address: 'Current Location',
          });
        },
        (error) => {
          console.error('Location error:', error);
        }
      );
    }
  }, []);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      
      const audioChunks: Blob[] = [];
      
      mediaRecorder.ondataavailable = (event) => {
        audioChunks.push(event.data);
      };
      
      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
        const audioUrl = URL.createObjectURL(audioBlob);
        
        setRecordingState(prev => ({
          ...prev,
          audioBlob,
          audioUrl,
          isRecording: false,
        }));
        
        // Stop the stream
        if (streamRef.current) {
          streamRef.current.getTracks().forEach(track => track.stop());
        }
      };
      
      mediaRecorder.start();
      setRecordingState(prev => ({ ...prev, isRecording: true, duration: 15 }));
      
      // Start countdown timer
      intervalRef.current = window.setInterval(() => {
        setRecordingState(prev => {
          const newDuration = prev.duration - 1;
          
          // Auto-stop at 0 seconds
          if (newDuration <= 0) {
            stopRecording();
            return { ...prev, duration: 0 };
          }
          
          return { ...prev, duration: newDuration };
        });
      }, 1000);
      
    } catch (error) {
      console.error('Error starting recording:', error);
      alert('Failed to start recording. Please check microphone permissions.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && recordingState.isRecording) {
      mediaRecorderRef.current.stop();
      
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    }
  };

  const playRecording = () => {
    if (recordingState.audioUrl && audioRef.current) {
      audioRef.current.src = recordingState.audioUrl;
      audioRef.current.play();
      setIsPlaying(true);
    }
  };

  const pauseRecording = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      setIsPlaying(false);
    }
  };

  const deleteRecording = () => {
    if (recordingState.audioUrl) {
      URL.revokeObjectURL(recordingState.audioUrl);
    }
    
    setRecordingState({
      isRecording: false,
      duration: 15, // Reset to 15 for countdown
    });
    setIsPlaying(false);
  };

  const saveRecording = async () => {
    if (!recordingState.audioBlob || !user) {
      return;
    }

    setIsSaving(true);
    
    try {
      // Convert emotion value to label
      const emotionLabel = emotionValue < 25 ? 'Sad' : 
                          emotionValue < 75 ? 'Mixed' : 
                          'Joy';

      // TODO: Upload audio to S3 and get URL
      const mockS3Url = `https://mock-s3-bucket.amazonaws.com/${user.userId}/${Date.now()}.wav`;

      // Calculate actual recording duration (15 - remaining time)
      const actualDuration = 15 - recordingState.duration;

      const echoData = {
        userId: user.userId,
        emotion: emotionLabel,
        s3Url: mockS3Url,
        location: location || undefined,
        tags: caption ? [caption] : [],
        duration: actualDuration,
        transcript: caption,
      };

      await saveEcho(echoData);
      
      // Reset form
      deleteRecording();
      setEmotionValue(50);
      setCaption('');
      
      // Navigate to echoes list
      navigate('/echoes');
      
    } catch (error) {
      console.error('Failed to save echo:', error);
      alert('Failed to save recording. Please try again.');
    } finally {
      setIsSaving(false);
    }
  };

  const formatDuration = (seconds: number) => {
    const secs = seconds % 60;
    return `0:${secs.toString().padStart(2, '0')}`;
  };

  const getSliderBackground = () => {
    const sadnessColor = '#1e40af'; // Dark blue
    const joyColor = '#ec4899'; // Pink
    const position = emotionValue;
    
    return `linear-gradient(to right, ${sadnessColor} 0%, #7c3aed ${position}%, ${joyColor} 100%)`;
  };

  const countWords = (text: string) => {
    return text.trim().split(/\s+/).filter(word => word.length > 0).length;
  };

  const handleCaptionChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newCaption = e.target.value;
    const wordCount = countWords(newCaption);
    
    if (wordCount <= 15) {
      setCaption(newCaption);
    }
  };

  return (
    <div className="p-3" style={{ maxWidth: '500px', margin: '0 auto' }}>
      <audio
        ref={audioRef}
        onEnded={() => setIsPlaying(false)}
        onPause={() => setIsPlaying(false)}
      />
      
      {/* Simple Header */}
      <div className="text-center mb-4">
        <h1 style={{ fontSize: '2rem', fontWeight: '600', marginBottom: '0.5rem' }}>
          Record Your Echo
        </h1>
        <p style={{ color: 'var(--text-secondary)' }}>
          Tap the button and speak (15 seconds max)
        </p>
      </div>

      {/* Recording Area */}
      <div className="card mb-4">
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
          {/* Duration Display */}
          <div style={{ 
            fontSize: '4rem', 
            fontFamily: 'monospace', 
            marginBottom: '2rem', 
            fontWeight: '300',
            textAlign: 'center',
            width: '100%'
          }}>
            {formatDuration(recordingState.duration)}
          </div>
          
          {/* Record Button - Always visible */}
          {!recordingState.isRecording && !recordingState.audioBlob && (
            <button
              onClick={startRecording}
              className="record-button"
              style={{ 
                width: '120px', 
                height: '120px', 
                fontSize: '1rem',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto'
              }}
            >
              <span style={{ display: 'block', fontSize: '2rem', lineHeight: '1' }}>●</span>
              <span style={{ fontSize: '0.8rem', marginTop: '0.25rem' }}>REC</span>
            </button>
          )}
          
          {/* Stop Button */}
          {recordingState.isRecording && (
            <button
              onClick={stopRecording}
              className="record-button recording"
              style={{ 
                width: '120px', 
                height: '120px', 
                fontSize: '1rem',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto'
              }}
            >
              <span style={{ display: 'block', fontSize: '2rem', lineHeight: '1' }}>■</span>
              <span style={{ fontSize: '0.8rem', marginTop: '0.25rem' }}>STOP</span>
            </button>
          )}
          
          {/* Playback Controls */}
          {recordingState.audioBlob && (
            <>
              <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'center', alignItems: 'center', width: '100%' }}>
                {!isPlaying ? (
                  <button onClick={playRecording} className="btn btn-primary">
                    ▶ Play
                  </button>
                ) : (
                  <button onClick={pauseRecording} className="btn btn-primary">
                    ⏸ Pause
                  </button>
                )}
                
                <button onClick={deleteRecording} className="btn btn-danger">
                  🗑 Delete
                </button>
              </div>

              {/* Emotion Slider */}
              <div className="mt-4">
                <label className="form-label">How are you feeling?</label>
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '0.5rem' }}>
                  <span style={{ color: '#1e40af', fontWeight: '600' }}>😢</span>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={emotionValue}
                    onChange={(e) => setEmotionValue(Number(e.target.value))}
                    style={{
                      width: '100%',
                      height: '8px',
                      borderRadius: '4px',
                      outline: 'none',
                      background: getSliderBackground(),
                      cursor: 'pointer',
                    }}
                  />
                  <span style={{ color: '#ec4899', fontWeight: '600' }}>😊</span>
                </div>
                <div className="text-center" style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                  {emotionValue < 25 ? 'Feeling sad' : 
                   emotionValue < 75 ? 'Mixed emotions' : 
                   'Feeling joyful'}
                </div>
              </div>

              {/* Caption Input */}
              <div className="form-group mt-4">
                <label htmlFor="caption" className="form-label">
                  Caption this moment (15 words or less)
                </label>
                <input
                  id="caption"
                  value={caption}
                  onChange={(e) => {
                    const words = e.target.value.trim().split(/\s+/);
                    if (words.length <= 15 || e.target.value === '') {
                      setCaption(e.target.value);
                    }
                  }}
                  placeholder="Describe what's happening..."
                  className="form-input"
                />
                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', textAlign: 'right', marginTop: '0.25rem' }}>
                  {caption.trim() ? caption.trim().split(/\s+/).length : 0}/15 words
                </div>
              </div>

              {/* Save Button */}
              <button
                onClick={saveRecording}
                disabled={isSaving}
                className="btn btn-primary"
                style={{ width: '100%', marginTop: '1rem', opacity: isSaving ? 0.6 : 1 }}
              >
                {isSaving ? '💾 Saving...' : '💾 Save Echo'}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default Record;