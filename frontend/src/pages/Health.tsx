import React, { useEffect, useState } from 'react';

interface DetailedHealthStatus {
  frontend: {
    status: 'healthy' | 'unhealthy';
    version: string;
    buildTime: string;
    environment: string;
  };
  backend: {
    status: 'healthy' | 'unhealthy' | 'unreachable';
    url: string;
    responseTime?: number;
    error?: string;
  };
  browser: {
    userAgent: string;
    language: string;
    onLine: boolean;
  };
  timestamp: string;
}

const Health: React.FC = () => {
  const [health, setHealth] = useState<DetailedHealthStatus>({
    frontend: {
      status: 'healthy',
      version: '0.0.0',
      buildTime: 'Unknown',
      environment: import.meta.env.MODE
    },
    backend: {
      status: 'unreachable',
      url: 'http://localhost:8000'
    },
    browser: {
      userAgent: navigator.userAgent,
      language: navigator.language,
      onLine: navigator.onLine
    },
    timestamp: new Date().toISOString()
  });

  useEffect(() => {
    const checkBackendHealth = async () => {
      const startTime = Date.now();
      try {
        const response = await fetch('http://localhost:8000/health');
        const responseTime = Date.now() - startTime;
        
        setHealth(prev => ({
          ...prev,
          backend: {
            ...prev.backend,
            status: response.ok ? 'healthy' : 'unhealthy',
            responseTime,
            error: undefined
          },
          timestamp: new Date().toISOString()
        }));
      } catch (error) {
        setHealth(prev => ({
          ...prev,
          backend: {
            ...prev.backend,
            status: 'unreachable',
            responseTime: undefined,
            error: error instanceof Error ? error.message : 'Unknown error'
          },
          timestamp: new Date().toISOString()
        }));
      }
    };

    checkBackendHealth();
    const interval = setInterval(checkBackendHealth, 10000); // Check every 10 seconds

    return () => clearInterval(interval);
  }, []);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy':
        return 'text-green-600';
      case 'unhealthy':
        return 'text-yellow-600';
      case 'unreachable':
        return 'text-red-600';
      default:
        return 'text-gray-600';
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-6">
      <h1 className="text-3xl font-bold mb-6">System Health Check</h1>
      
      <div className="space-y-6">
        {/* Frontend Status */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4">Frontend Status</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-sm text-gray-600">Status</p>
              <p className={`font-medium ${getStatusColor(health.frontend.status)}`}>
                {health.frontend.status.toUpperCase()}
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Environment</p>
              <p className="font-medium">{health.frontend.environment}</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Version</p>
              <p className="font-medium">{health.frontend.version}</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">URL</p>
              <p className="font-medium">{window.location.origin}</p>
            </div>
          </div>
        </div>

        {/* Backend Status */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4">Backend Status</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-sm text-gray-600">Status</p>
              <p className={`font-medium ${getStatusColor(health.backend.status)}`}>
                {health.backend.status.toUpperCase()}
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-600">URL</p>
              <p className="font-medium">{health.backend.url}</p>
            </div>
            {health.backend.responseTime && (
              <div>
                <p className="text-sm text-gray-600">Response Time</p>
                <p className="font-medium">{health.backend.responseTime}ms</p>
              </div>
            )}
            {health.backend.error && (
              <div className="col-span-2">
                <p className="text-sm text-gray-600">Error</p>
                <p className="font-medium text-red-600">{health.backend.error}</p>
              </div>
            )}
          </div>
        </div>

        {/* Browser Information */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4">Browser Information</h2>
          <div className="space-y-2">
            <div>
              <p className="text-sm text-gray-600">Online Status</p>
              <p className={`font-medium ${health.browser.onLine ? 'text-green-600' : 'text-red-600'}`}>
                {health.browser.onLine ? 'ONLINE' : 'OFFLINE'}
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Language</p>
              <p className="font-medium">{health.browser.language}</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">User Agent</p>
              <p className="font-medium text-sm break-all">{health.browser.userAgent}</p>
            </div>
          </div>
        </div>

        {/* Last Update */}
        <div className="text-center text-sm text-gray-500">
          Last updated: {new Date(health.timestamp).toLocaleString()}
        </div>
      </div>
    </div>
  );
};

export default Health;