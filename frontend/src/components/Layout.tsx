import React, { useState } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const Layout: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [email, setEmail] = useState('');
  const [isLoading, setIsLoading] = useState(false);

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
            
            <form onSubmit={async (e) => {
              e.preventDefault();
              if (!email.trim()) {
                alert('Please enter an email address');
                return;
              }
              
              setIsLoading(true);
              try {
                // First try to create user (will fail if already exists)
                await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/v1/auth/users/create`, {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ 
                    email: email.trim(), 
                    username: email.split('@')[0] 
                  })
                }).catch(() => {}); // Ignore if user already exists
                
                // Login to get JWT token
                const loginResponse = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/v1/auth/login`, {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ email: email.trim() })
                });
                
                if (loginResponse.ok) {
                  const data = await loginResponse.json();
                  
                  // Store user and token
                  const demoUser = {
                    userId: data.user.user_id,
                    email: data.user.email,
                    name: data.user.username || email.split('@')[0],
                    createdAt: new Date().toISOString()
                  };
                  localStorage.setItem('echoes_user', JSON.stringify(demoUser));
                  localStorage.setItem('echoes_auth_token', data.access_token);
                  window.location.reload();
                } else {
                  alert('Failed to login. Please try again.');
                }
              } catch (error) {
                console.error('Demo login error:', error);
                alert('Failed to connect to server. Please try again.');
              } finally {
                setIsLoading(false);
              }
            }}>
              <div className="form-group mb-3">
                <label htmlFor="email" className="form-label">Email Address</label>
                <input
                  type="email"
                  id="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="Enter your email"
                  className="form-input"
                  required
                  disabled={isLoading}
                />
              </div>
              
              <button
                type="submit"
                className="btn btn-primary"
                style={{ width: '100%' }}
                disabled={isLoading}
              >
                {isLoading ? 'Signing in...' : 'Sign In'}
              </button>
              
              <div className="text-center mt-3">
                <button
                  type="button"
                  onClick={() => setEmail('demo@echoes.app')}
                  className="btn btn-link"
                  style={{ fontSize: '0.875rem', padding: '0.25rem 0.5rem' }}
                  disabled={isLoading}
                >
                  Use demo account
                </button>
              </div>
            </form>
            
            <p className="text-center mt-3" style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
              No password required for demo accounts
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