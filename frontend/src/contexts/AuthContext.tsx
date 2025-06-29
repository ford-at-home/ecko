import React, { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import { type User } from '../types';
import { authService } from '../services/authService';

interface AuthContextType {
  user: User | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  register: (email: string, password: string, name: string) => Promise<void>;
  loading: boolean;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check for demo user in localStorage first
    const storedUser = localStorage.getItem('echoes_user');
    if (storedUser) {
      try {
        const demoUser = JSON.parse(storedUser);
        // Check if we also have a valid token
        const token = localStorage.getItem('echoes_auth_token');
        if (token) {
          setUser(demoUser);
          setLoading(false);
          return;
        } else {
          // No token, clear user
          localStorage.removeItem('echoes_user');
        }
      } catch (error) {
        console.error('Failed to parse stored user:', error);
        localStorage.removeItem('echoes_user');
        localStorage.removeItem('echoes_auth_token');
      }
    }

    // Check for existing authenticated user
    const currentUser = authService.getCurrentUser();
    if (currentUser && authService.isAuthenticatedSync()) {
      // Convert CognitoUser to User type
      const user: User = {
        userId: currentUser.userId,
        email: currentUser.email,
        name: currentUser.name || currentUser.email.split('@')[0],
        createdAt: new Date().toISOString(), // This would come from Cognito attributes
      };
      setUser(user);
    }
    setLoading(false);
  }, []);

  const login = async (email: string, password: string) => {
    setLoading(true);
    try {
      // Authenticate with Cognito through auth service
      const cognitoUser = await authService.login({ email, password });
      
      // Convert CognitoUser to User type
      const user: User = {
        userId: cognitoUser.userId,
        email: cognitoUser.email,
        name: cognitoUser.name || cognitoUser.email.split('@')[0],
        createdAt: new Date().toISOString(),
      };
      
      setUser(user);
    } catch (error) {
      console.error('Login failed:', error);
      throw error;
    } finally {
      setLoading(false);
    }
  };

  const register = async (email: string, password: string, name: string) => {
    setLoading(true);
    try {
      // Register with Cognito through auth service
      const cognitoUser = await authService.register({ email, password, name });
      
      // Convert CognitoUser to User type
      const user: User = {
        userId: cognitoUser.userId,
        email: cognitoUser.email,
        name: cognitoUser.name || name,
        createdAt: new Date().toISOString(),
      };
      
      setUser(user);
    } catch (error) {
      console.error('Registration failed:', error);
      throw error;
    } finally {
      setLoading(false);
    }
  };

  const logout = async () => {
    try {
      // Clear demo user and tokens from localStorage
      localStorage.removeItem('echoes_user');
      localStorage.removeItem('echoes_auth_token');
      
      // Try to logout from Cognito if authenticated
      if (authService.isAuthenticated()) {
        await authService.logout();
      }
      
      setUser(null);
    } catch (error) {
      console.error('Logout failed:', error);
      // Still clear local state even if logout fails
      localStorage.removeItem('echoes_user');
      localStorage.removeItem('echoes_auth_token');
      setUser(null);
    }
  };

  const value = {
    user,
    login,
    logout,
    register,
    loading,
    isAuthenticated: !!user && (!!localStorage.getItem('echoes_user') || authService.isAuthenticatedSync()),
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};