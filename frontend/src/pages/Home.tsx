import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useEchoes } from '../contexts/EchoContext';
import { EMOTION_TAGS, type Echo } from '../types';

const Home: React.FC = () => {
  const navigate = useNavigate();
  const { getRandomEcho, setCurrentEcho } = useEchoes();
  const [selectedEmotion, setSelectedEmotion] = useState<string>('');
  const [suggestedEcho, setSuggestedEcho] = useState<Echo | null>(null);
  const [isSearching, setIsSearching] = useState(false);

  const handleEmotionSelect = async (emotion: string) => {
    setSelectedEmotion(emotion);
    setIsSearching(true);
    
    try {
      const echo = await getRandomEcho(emotion);
      setSuggestedEcho(echo);
    } catch (error) {
      console.error('Failed to get echo:', error);
    } finally {
      setIsSearching(false);
    }
  };

  const handlePlayEcho = (echo: Echo) => {
    setCurrentEcho(echo);
    navigate(`/playback/${echo.echoId}`);
  };

  const formatTimeAgo = (timestamp: string) => {
    const now = new Date();
    const echoTime = new Date(timestamp);
    const diffInHours = Math.floor((now.getTime() - echoTime.getTime()) / (1000 * 60 * 60));
    
    if (diffInHours < 24) {
      return `${diffInHours} hours ago`;
    } else {
      const diffInDays = Math.floor(diffInHours / 24);
      return `${diffInDays} days ago`;
    }
  };

  return (
    <div className="p-3">
      {/* Welcome Header */}
      <div className="glass p-4 mb-4 text-center">
        <h1 className="mb-2" style={{ fontSize: '2.5rem', fontWeight: '700' }}>
          How are you feeling today?
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '1.125rem' }}>
          Tell us your mood and we'll resurface a matching memory
        </p>
      </div>

      {/* Emotion Selection */}
      <div className="card mb-4">
        <h2 className="mb-3" style={{ fontSize: '1.25rem', fontWeight: '600' }}>I feel...</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.75rem' }}>
          {EMOTION_TAGS.map((emotion) => (
            <button
              key={emotion.id}
              onClick={() => handleEmotionSelect(emotion.label)}
              disabled={isSearching}
              className={`emotion-tag ${selectedEmotion === emotion.label ? 'selected' : ''}`}
              style={{ opacity: isSearching ? 0.6 : 1 }}
            >
              <span style={{ fontSize: '1.25rem' }}>{emotion.emoji}</span>
              <span>{emotion.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Search Status */}
      {isSearching && (
        <div className="glass p-4 text-center mb-4">
          <div className="loading-spinner" style={{ margin: '0 auto 1rem' }}></div>
          <p>🔊 Searching for echoes that match your mood...</p>
        </div>
      )}

      {/* Suggested Echo */}
      {suggestedEcho && !isSearching && (
        <div className="glass p-4 mb-4">
          <div className="flex justify-between items-center mb-3">
            <h3 style={{ fontSize: '1.125rem', fontWeight: '600' }}>
              Echo Found - {selectedEmotion}
            </h3>
            <button
              onClick={() => handlePlayEcho(suggestedEcho)}
              className="btn btn-primary"
            >
              ▶ Play
            </button>
          </div>
          
          <div className="echo-meta">
            <div className="flex items-center gap-2">
              <strong>Emotion:</strong>
              <span>{EMOTION_TAGS.find(tag => tag.label === suggestedEcho.emotion)?.emoji || '🌀'} {suggestedEcho.emotion}</span>
            </div>
            <div className="flex items-center gap-2">
              <strong>Recorded:</strong>
              <span>{formatTimeAgo(suggestedEcho.timestamp)}</span>
            </div>
            
            {suggestedEcho.location?.address && (
              <div className="flex items-center gap-2">
                <strong>Location:</strong>
                <span>📍 {suggestedEcho.location.address}</span>
              </div>
            )}
            
            {suggestedEcho.transcript && (
              <div className="echo-transcript">
                "{suggestedEcho.transcript}"
              </div>
            )}
            
            <div className="flex items-center gap-2">
              <strong>Duration:</strong>
              <span>{suggestedEcho.duration} seconds</span>
            </div>
            
            {suggestedEcho.tags && suggestedEcho.tags.length > 0 && (
              <div className="flex items-center gap-2 flex-wrap">
                <strong>Tags:</strong>
                {suggestedEcho.tags.map(tag => (
                  <span key={tag} className="emotion-tag" style={{ padding: '0.25rem 0.75rem', fontSize: '0.875rem' }}>
                    #{tag}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* No Echo Found */}
      {selectedEmotion && !suggestedEcho && !isSearching && (
        <div className="glass p-4 text-center mb-4">
          <p className="mb-3">No echoes found for "{selectedEmotion}" yet.</p>
          <button onClick={() => navigate('/record')} className="btn btn-primary">
            Create your first {selectedEmotion.toLowerCase()} echo
          </button>
        </div>
      )}

      {/* Quick Actions */}
      <div className="echo-grid mt-4">
        <div className="card text-center">
          <div className="mb-3" style={{ fontSize: '3rem' }}>🎙️</div>
          <h3 className="mb-2" style={{ fontSize: '1.25rem', fontWeight: '600' }}>
            Capture This Moment
          </h3>
          <p className="mb-3" style={{ color: 'var(--text-secondary)' }}>
            Record a new echo
          </p>
          <button onClick={() => navigate('/record')} className="btn btn-primary">
            Go to Recorder
          </button>
        </div>
        
        <div className="card text-center">
          <div className="mb-3" style={{ fontSize: '3rem' }}>🔊</div>
          <h3 className="mb-2" style={{ fontSize: '1.25rem', fontWeight: '600' }}>
            Browse Memories
          </h3>
          <p className="mb-3" style={{ color: 'var(--text-secondary)' }}>
            View all your echoes
          </p>
          <button onClick={() => navigate('/echoes')} className="btn btn-primary">
            View Collection
          </button>
        </div>
      </div>
    </div>
  );
};

export default Home;