import React from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const Layout: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  const isActive = (path: string) => {
    return location.pathname === path;
  };

  if (!user) {
    return (
      <div className="flex items-center justify-center" style={{ minHeight: '100vh' }}>
        <div className="glass p-4" style={{ maxWidth: '400px', width: '100%', margin: '0 1rem' }}>
          <div className="text-center mb-4">
            <h1 className="mb-2" style={{ fontSize: '2rem', fontWeight: '700' }}>🌀 Echoes</h1>
            <p style={{ color: 'var(--text-secondary)' }}>Your soulful audio time machine</p>
          </div>
          
          <div className="card p-4">
            <h2 className="mb-3" style={{ fontSize: '1.5rem', fontWeight: '600' }}>Welcome Back</h2>
            <p className="mb-4" style={{ color: 'var(--text-secondary)' }}>
              Sign in to access your audio memories
            </p>
            
            <button
              onClick={() => {
                // Simple demo login
                const demoUser = {
                  userId: 'demo_user',
                  email: 'demo@echoes.app',
                  name: 'Demo User',
                  createdAt: new Date().toISOString()
                };
                localStorage.setItem('echoes_user', JSON.stringify(demoUser));
                window.location.reload();
              }}
              className="btn btn-primary"
              style={{ width: '100%' }}
            >
              Enter Demo Mode
            </button>
            
            <p className="text-center mt-3" style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
              Full authentication coming soon
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <>
      {/* Navigation */}
      <nav className="nav-bar">
        <div className="nav-container">
          <a href="/" className="nav-brand">
            🌀 Echoes
          </a>
          
          <div className="nav-links">
            <a 
              href="/"
              className={`nav-link ${isActive('/') ? 'active' : ''}`}
              onClick={(e) => { e.preventDefault(); navigate('/'); }}
            >
              Record
            </a>
            <a 
              href="/echoes"
              className={`nav-link ${isActive('/echoes') ? 'active' : ''}`}
              onClick={(e) => { e.preventDefault(); navigate('/echoes'); }}
            >
              My Echoes
            </a>
            <button 
              onClick={logout}
              className="btn btn-secondary"
              style={{ padding: '0.5rem 1rem' }}
            >
              Logout
            </button>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="app-container flex-1">
        <Outlet />
      </main>

      {/* Status Bar */}
      <footer className="status-bar">
        <div className="status-item">
          <span>👤 {user.name}</span>
        </div>
        <div className="status-item">
          <span>📍 {location.pathname}</span>
        </div>
      </footer>
    </>
  );
};

export default Layout;