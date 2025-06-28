import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useEchoes } from '../contexts/EchoContext';
import { type Echo } from '../types';

const EchoList: React.FC = () => {
  const navigate = useNavigate();
  const { echoes, loading, fetchEchoes, setCurrentEcho } = useEchoes();

  useEffect(() => {
    fetchEchoes();
  }, []);

  const handlePlayEcho = (echo: Echo) => {
    setCurrentEcho(echo);
    navigate(`/playback/${echo.echoId}`);
  };

  const formatDate = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center" style={{ minHeight: '400px' }}>
        <div className="text-center">
          <div className="loading-spinner" style={{ margin: '0 auto 1rem' }}></div>
          <p>Loading your echoes...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-3">
      {/* Simple Header */}
      <div className="text-center mb-4">
        <h1 style={{ fontSize: '1.5rem', fontWeight: '600', marginBottom: '0.5rem' }}>
          My Echoes ({echoes.length})
        </h1>
      </div>

      {/* Simple Echo Cards */}
      {echoes.length === 0 ? (
        <div className="glass p-4 text-center">
          <p className="mb-4">No echoes yet</p>
          <button onClick={() => navigate('/')} className="btn btn-primary">
            Record Your First Echo
          </button>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '1rem' }}>
          {echoes.map((echo) => (
            <div key={echo.echoId} className="card" style={{ padding: '1rem' }}>
              {/* Play Button */}
              <div className="text-center mb-3">
                <button
                  onClick={() => handlePlayEcho(echo)}
                  className="record-button"
                  style={{ 
                    width: '60px', 
                    height: '60px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    margin: '0 auto'
                  }}
                >
                  ▶
                </button>
              </div>

              {/* Date */}
              <div className="text-center mb-2">
                <strong>{formatDate(echo.timestamp)}</strong>
              </div>

              {/* Location */}
              {echo.location?.address && (
                <div className="text-center mb-2" style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                  📍 {echo.location.address}
                </div>
              )}

              {/* Caption */}
              {echo.transcript && (
                <div className="text-center" style={{ 
                  fontSize: '0.875rem', 
                  color: 'var(--text-secondary)', 
                  fontStyle: 'italic',
                  lineHeight: '1.3'
                }}>
                  "{echo.transcript}"
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default EchoList;