/**
 * Authentication Service
 * Handles AWS Cognito authentication and JWT token management
 */

import { config } from '../config';
import { apiClient } from '../utils/apiClient';

export interface CognitoUser {
  userId: string;
  email: string;
  name?: string;
  attributes?: Record<string, string>;
}

export interface AuthTokens {
  idToken: string;
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterCredentials extends LoginCredentials {
  name: string;
}

class AuthService {
  private tokenKey = 'echoes_auth_token';
  private userKey = 'echoes_user';
  private refreshKey = 'echoes_refresh_token';

  /**
   * Initialize authentication service
   */
  constructor() {
    // Check for existing token on initialization
    const token = this.getStoredToken();
    if (token) {
      apiClient.setAuthToken(token);
    }
  }

  /**
   * Login user with Cognito
   * For now, this is a mock implementation that should be replaced with actual Cognito SDK
   */
  async login(credentials: LoginCredentials): Promise<CognitoUser> {
    try {
      // TODO: Replace with actual Cognito authentication
      // For development, we'll use a mock authentication endpoint
      
      // Mock authentication for development
      if (config.features.debug) {
        console.log('Debug mode: Using mock authentication');
        
        // Generate mock tokens
        const mockTokens: AuthTokens = {
          idToken: `mock_id_token_${Date.now()}`,
          accessToken: `mock_access_token_${Date.now()}`,
          refreshToken: `mock_refresh_token_${Date.now()}`,
          expiresIn: 3600, // 1 hour
        };

        const mockUser: CognitoUser = {
          userId: `user_${Date.now()}`,
          email: credentials.email,
          name: credentials.email.split('@')[0],
        };

        // Store tokens and user
        this.storeTokens(mockTokens);
        this.storeUser(mockUser);

        // Set token in API client
        apiClient.setAuthToken(mockTokens.idToken);

        return mockUser;
      }

      // Production Cognito authentication would go here
      throw new Error('Cognito authentication not yet implemented');
    } catch (error) {
      console.error('Login failed:', error);
      throw error;
    }
  }

  /**
   * Register new user with Cognito
   */
  async register(credentials: RegisterCredentials): Promise<CognitoUser> {
    try {
      // TODO: Replace with actual Cognito registration
      
      // Mock registration for development
      if (config.features.debug) {
        console.log('Debug mode: Using mock registration');
        
        // Generate mock tokens
        const mockTokens: AuthTokens = {
          idToken: `mock_id_token_${Date.now()}`,
          accessToken: `mock_access_token_${Date.now()}`,
          refreshToken: `mock_refresh_token_${Date.now()}`,
          expiresIn: 3600, // 1 hour
        };

        const mockUser: CognitoUser = {
          userId: `user_${Date.now()}`,
          email: credentials.email,
          name: credentials.name,
        };

        // Store tokens and user
        this.storeTokens(mockTokens);
        this.storeUser(mockUser);

        // Set token in API client
        apiClient.setAuthToken(mockTokens.idToken);

        return mockUser;
      }

      // Production Cognito registration would go here
      throw new Error('Cognito registration not yet implemented');
    } catch (error) {
      console.error('Registration failed:', error);
      throw error;
    }
  }

  /**
   * Logout user
   */
  async logout(): Promise<void> {
    try {
      // Clear stored tokens and user data
      localStorage.removeItem(this.tokenKey);
      localStorage.removeItem(this.userKey);
      localStorage.removeItem(this.refreshKey);

      // Clear token from API client
      apiClient.setAuthToken(null);

      // TODO: Call Cognito logout if needed
    } catch (error) {
      console.error('Logout failed:', error);
      throw error;
    }
  }

  /**
   * Refresh authentication token
   */
  async refreshToken(): Promise<AuthTokens | null> {
    try {
      const refreshToken = localStorage.getItem(this.refreshKey);
      if (!refreshToken) {
        return null;
      }

      // TODO: Implement actual token refresh with Cognito
      if (config.features.debug) {
        console.log('Debug mode: Mock token refresh');
        
        const newTokens: AuthTokens = {
          idToken: `mock_id_token_refreshed_${Date.now()}`,
          accessToken: `mock_access_token_refreshed_${Date.now()}`,
          refreshToken: refreshToken,
          expiresIn: 3600,
        };

        this.storeTokens(newTokens);
        apiClient.setAuthToken(newTokens.idToken);

        return newTokens;
      }

      return null;
    } catch (error) {
      console.error('Token refresh failed:', error);
      return null;
    }
  }

  /**
   * Get current user
   */
  getCurrentUser(): CognitoUser | null {
    const userJson = localStorage.getItem(this.userKey);
    if (!userJson) {
      return null;
    }

    try {
      return JSON.parse(userJson);
    } catch (error) {
      console.error('Failed to parse stored user:', error);
      return null;
    }
  }

  /**
   * Check if user is authenticated
   */
  isAuthenticated(): boolean {
    return !!this.getStoredToken();
  }

  /**
   * Get stored authentication token
   */
  getStoredToken(): string | null {
    return localStorage.getItem(this.tokenKey);
  }

  /**
   * Store authentication tokens
   */
  private storeTokens(tokens: AuthTokens): void {
    localStorage.setItem(this.tokenKey, tokens.idToken);
    localStorage.setItem(this.refreshKey, tokens.refreshToken);
    
    // Store token expiration time
    const expirationTime = Date.now() + (tokens.expiresIn * 1000);
    localStorage.setItem(`${this.tokenKey}_expires`, String(expirationTime));
  }

  /**
   * Store user data
   */
  private storeUser(user: CognitoUser): void {
    localStorage.setItem(this.userKey, JSON.stringify(user));
  }

  /**
   * Check if token is expired
   */
  isTokenExpired(): boolean {
    const expirationTime = localStorage.getItem(`${this.tokenKey}_expires`);
    if (!expirationTime) {
      return true;
    }

    return Date.now() > parseInt(expirationTime, 10);
  }

  /**
   * Setup automatic token refresh
   */
  setupTokenRefresh(): void {
    // Check token expiration every minute
    setInterval(async () => {
      if (this.isAuthenticated() && this.isTokenExpired()) {
        console.log('Token expired, attempting refresh...');
        await this.refreshToken();
      }
    }, 60000); // 1 minute
  }
}

// Create and export singleton instance
export const authService = new AuthService();

// Setup token refresh on initialization
authService.setupTokenRefresh();

export default authService;