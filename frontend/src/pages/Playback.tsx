import React, { useState, useRef, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useEchoes } from '../contexts/EchoContext';
import { EMOTION_TAGS } from '../types';

const Playback: React.FC = () => {
  const { echoId } = useParams<{ echoId: string }>();
  const navigate = useNavigate();
  const { echoes, currentEcho } = useEchoes();

  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [isFavorite, setIsFavorite] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Find the echo to play
  const echo = currentEcho || echoes.find(e => e.echoId === echoId);

  useEffect(() => {
    if (!echo) {
      navigate('/echoes');
      return;
    }

    // Initialize audio
    if (audioRef.current) {
      audioRef.current.addEventListener('timeupdate', handleTimeUpdate);
      audioRef.current.addEventListener('ended', handleAudioEnd);
    }

    return () => {
      if (audioRef.current) {
        audioRef.current.removeEventListener('timeupdate', handleTimeUpdate);
        audioRef.current.removeEventListener('ended', handleAudioEnd);
      }
    };
  }, [echo, navigate]);

  const handleTimeUpdate = () => {
    if (audioRef.current) {
      setCurrentTime(audioRef.current.currentTime);
    }
  };

  const handleAudioEnd = () => {
    setIsPlaying(false);
    setCurrentTime(0);
  };

  const togglePlayback = () => {
    if (!audioRef.current) return;

    if (isPlaying) {
      audioRef.current.pause();
    } else {
      audioRef.current.play();
    }
    setIsPlaying(!isPlaying);
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const formatDate = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  if (!echo) {
    return (
      <div className="flex items-center justify-center" style={{ minHeight: '400px' }}>
        <div className="text-center">
          <div className="loading-spinner" style={{ margin: '0 auto 1rem' }}></div>
          <p>Loading echo...</p>
        </div>
      </div>
    );
  }

  const emotionTag = EMOTION_TAGS.find(tag => tag.label === echo.emotion);
  const progressPercent = echo.duration > 0 ? (currentTime / echo.duration) * 100 : 0;

  return (
    <div className="p-3">
      {/* Header */}
      <div className="glass p-4 mb-4">
        <div className="flex justify-between items-center mb-3">
          <button onClick={() => navigate('/echoes')} className="btn btn-secondary">
            ← Back to Echoes
          </button>
          <button 
            onClick={() => setIsFavorite(!isFavorite)}
            className="btn btn-secondary"
          >
            {isFavorite ? '❤️' : '🤍'} Favorite
          </button>
        </div>
      </div>

      {/* Audio Player */}
      <div className="glass p-4 mb-4">
        <audio ref={audioRef} src={echo.s3Url} />
        
        {/* Emotion Display */}
        <div className="text-center mb-4">
          <div style={{ fontSize: '4rem', marginBottom: '0.5rem' }}>{emotionTag?.emoji || '🌀'}</div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: '600' }}>{echo.emotion}</h2>
        </div>

        {/* Play Controls */}
        <div className="text-center mb-4">
          <button
            onClick={togglePlayback}
            className="record-button"
            style={{ width: '100px', height: '100px' }}
          >
            {isPlaying ? '⏸' : '▶'}
          </button>
        </div>

        {/* Progress Bar */}
        <div className="mb-3">
          <div style={{ 
            height: '8px', 
            background: 'var(--surface-light)', 
            borderRadius: '4px',
            overflow: 'hidden'
          }}>
            <div style={{
              height: '100%',
              background: 'var(--primary)',
              width: `${progressPercent}%`,
              transition: 'width 0.1s linear'
            }} />
          </div>
          <div className="flex justify-between mt-2" style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
            <span>{formatTime(currentTime)}</span>
            <span>{formatTime(echo.duration)}</span>
          </div>
        </div>
      </div>

      {/* Echo Details */}
      <div className="card">
        <h3 className="mb-3" style={{ fontSize: '1.125rem', fontWeight: '600' }}>Echo Details</h3>
        
        <div className="echo-meta">
          <div className="flex items-center gap-2">
            <strong>📅 Recorded:</strong>
            <span>{formatDate(echo.timestamp)}</span>
          </div>

          {echo.location?.address && (
            <div className="flex items-center gap-2">
              <strong>📍 Location:</strong>
              <span>{echo.location.address}</span>
            </div>
          )}

          {echo.transcript && (
            <div className="echo-transcript">
              "{echo.transcript}"
            </div>
          )}

          {echo.tags && echo.tags.length > 0 && (
            <div className="flex items-center gap-2 flex-wrap">
              <strong>🏷️ Tags:</strong>
              {echo.tags.map(tag => (
                <span 
                  key={tag} 
                  className="emotion-tag" 
                  style={{ padding: '0.25rem 0.75rem', fontSize: '0.875rem' }}
                >
                  #{tag}
                </span>
              ))}
            </div>
          )}

          {echo.detectedMood && (
            <div className="flex items-center gap-2">
              <strong>🎯 Detected Mood:</strong>
              <span>{echo.detectedMood}</span>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex gap-2 mt-4">
          <button className="btn btn-primary">
            🔊 Share Echo
          </button>
          <button className="btn btn-secondary">
            📥 Download
          </button>
        </div>
      </div>
    </div>
  );
};

export default Playback;