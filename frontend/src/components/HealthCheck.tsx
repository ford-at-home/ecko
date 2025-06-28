import React, { useEffect, useState } from 'react';

interface HealthStatus {
  frontend: boolean;
  backend: boolean;
  backendUrl: string;
  timestamp: string;
}

const HealthCheck: React.FC = () => {
  const [health, setHealth] = useState<HealthStatus>({
    frontend: true,
    backend: false,
    backendUrl: 'http://localhost:8000',
    timestamp: new Date().toISOString()
  });

  useEffect(() => {
    const checkBackendHealth = async () => {
      try {
        const response = await fetch('http://localhost:8000/health');
        setHealth(prev => ({
          ...prev,
          backend: response.ok,
          timestamp: new Date().toISOString()
        }));
      } catch (error) {
        setHealth(prev => ({
          ...prev,
          backend: false,
          timestamp: new Date().toISOString()
        }));
      }
    };

    checkBackendHealth();
    const interval = setInterval(checkBackendHealth, 30000); // Check every 30 seconds

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="fixed bottom-4 right-4 bg-white rounded-lg shadow-lg p-4 text-sm">
      <h3 className="font-semibold mb-2">System Health</h3>
      <div className="space-y-1">
        <div className="flex items-center">
          <span className={`w-2 h-2 rounded-full mr-2 ${health.frontend ? 'bg-green-500' : 'bg-red-500'}`}></span>
          <span>Frontend: {health.frontend ? 'Running' : 'Error'}</span>
        </div>
        <div className="flex items-center">
          <span className={`w-2 h-2 rounded-full mr-2 ${health.backend ? 'bg-green-500' : 'bg-red-500'}`}></span>
          <span>Backend: {health.backend ? 'Connected' : 'Disconnected'}</span>
        </div>
        <div className="text-xs text-gray-500 mt-2">
          Last check: {new Date(health.timestamp).toLocaleTimeString()}
        </div>
      </div>
    </div>
  );
};

export default HealthCheck;