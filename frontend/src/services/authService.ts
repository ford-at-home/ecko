/**
 * Authentication Service
 * Handles AWS Cognito authentication and JWT token management
 */

import { Amplify } from 'aws-amplify';
import { Auth } from '@aws-amplify/auth';
import { config } from '../config';
import { apiClient } from '../utils/apiClient';

// Configure Amplify with Cognito settings
Amplify.configure({
  Auth: {
    region: config.cognito.region,
    userPoolId: config.cognito.userPoolId,
    userPoolWebClientId: config.cognito.clientId,
  },
});

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
   */
  async login(credentials: LoginCredentials): Promise<CognitoUser> {
    try {
      // Authenticate with Cognito
      const signInResult = await Auth.signIn(credentials.email, credentials.password);
      
      // Get user attributes
      const attributes = signInResult.attributes || {};
      
      // Get current session to retrieve tokens
      const session = await Auth.currentSession();
      
      // Extract tokens
      const tokens: AuthTokens = {
        idToken: session.getIdToken().getJwtToken(),
        accessToken: session.getAccessToken().getJwtToken(),
        refreshToken: session.getRefreshToken().getToken(),
        expiresIn: 3600, // 1 hour default
      };
      
      // Create user object
      const user: CognitoUser = {
        userId: attributes.sub || signInResult.username,
        email: attributes.email || credentials.email,
        name: attributes.name || attributes.given_name || credentials.email.split('@')[0],
        attributes,
      };
      
      // Store tokens and user
      this.storeTokens(tokens);
      this.storeUser(user);
      
      // Set token in API client
      apiClient.setAuthToken(tokens.idToken);
      
      return user;
    } catch (error: any) {
      console.error('Login failed:', error);
      
      // Handle specific Cognito errors
      if (error.code === 'UserNotConfirmedException') {
        throw new Error('Please verify your email before logging in.');
      } else if (error.code === 'NotAuthorizedException') {
        throw new Error('Invalid email or password.');
      } else if (error.code === 'UserNotFoundException') {
        throw new Error('No account found with this email.');
      }
      
      throw new Error(error.message || 'Login failed. Please try again.');
    }
  }

  /**
   * Register new user with Cognito
   */
  async register(credentials: RegisterCredentials): Promise<CognitoUser> {
    try {
      // Register with Cognito
      const signUpResult = await Auth.signUp({
        username: credentials.email,
        password: credentials.password,
        attributes: {
          email: credentials.email,
          name: credentials.name,
        },
      });
      
      // Create user object (user needs to verify email before full authentication)
      const user: CognitoUser = {
        userId: signUpResult.userSub,
        email: credentials.email,
        name: credentials.name,
      };
      
      // Note: User needs to verify email before they can login
      // Don't store tokens yet as user isn't authenticated
      
      return user;
    } catch (error: any) {
      console.error('Registration failed:', error);
      
      // Handle specific Cognito errors
      if (error.code === 'UsernameExistsException') {
        throw new Error('An account with this email already exists.');
      } else if (error.code === 'InvalidPasswordException') {
        throw new Error('Password does not meet requirements. Use at least 8 characters with uppercase, lowercase, numbers, and symbols.');
      } else if (error.code === 'InvalidParameterException') {
        throw new Error('Invalid email format.');
      }
      
      throw new Error(error.message || 'Registration failed. Please try again.');
    }
  }

  /**
   * Logout user
   */
  async logout(): Promise<void> {
    try {
      // Sign out from Cognito
      await Auth.signOut();
      
      // Clear stored tokens and user data
      localStorage.removeItem(this.tokenKey);
      localStorage.removeItem(this.userKey);
      localStorage.removeItem(this.refreshKey);
      localStorage.removeItem(`${this.tokenKey}_expires`);

      // Clear token from API client
      apiClient.setAuthToken(null);
    } catch (error) {
      console.error('Logout failed:', error);
      // Still clear local data even if Cognito logout fails
      localStorage.removeItem(this.tokenKey);
      localStorage.removeItem(this.userKey);
      localStorage.removeItem(this.refreshKey);
      localStorage.removeItem(`${this.tokenKey}_expires`);
      apiClient.setAuthToken(null);
    }
  }

  /**
   * Refresh authentication token
   */
  async refreshToken(): Promise<AuthTokens | null> {
    try {
      // Get current authenticated user
      const cognitoUser = await Auth.currentAuthenticatedUser();
      if (!cognitoUser) {
        return null;
      }
      
      // Get refreshed session
      const session = await Auth.currentSession();
      
      // Extract new tokens
      const tokens: AuthTokens = {
        idToken: session.getIdToken().getJwtToken(),
        accessToken: session.getAccessToken().getJwtToken(),
        refreshToken: session.getRefreshToken().getToken(),
        expiresIn: 3600,
      };
      
      // Store new tokens
      this.storeTokens(tokens);
      apiClient.setAuthToken(tokens.idToken);
      
      return tokens;
    } catch (error) {
      console.error('Token refresh failed:', error);
      return null;
    }
  }

  /**
   * Get current user
   */
  getCurrentUser(): CognitoUser | null {
    // First check localStorage for cached user
    const userJson = localStorage.getItem(this.userKey);
    if (userJson) {
      try {
        return JSON.parse(userJson);
      } catch (error) {
        console.error('Failed to parse stored user:', error);
      }
    }
    
    // If no cached user, try to get from Cognito
    this.fetchCurrentUser();
    return null;
  }
  
  /**
   * Fetch current user from Cognito
   */
  private async fetchCurrentUser(): Promise<CognitoUser | null> {
    try {
      const cognitoUser = await Auth.currentAuthenticatedUser();
      const attributes = await Auth.userAttributes(cognitoUser);
      
      // Convert attributes array to object
      const attributesObj: Record<string, string> = {};
      attributes.forEach(attr => {
        attributesObj[attr.Name] = attr.Value;
      });
      
      const user: CognitoUser = {
        userId: attributesObj.sub || cognitoUser.username,
        email: attributesObj.email || '',
        name: attributesObj.name || attributesObj.given_name || '',
        attributes: attributesObj,
      };
      
      // Cache the user
      this.storeUser(user);
      
      // Get and set the current token
      const session = await Auth.currentSession();
      apiClient.setAuthToken(session.getIdToken().getJwtToken());
      
      return user;
    } catch (error) {
      console.error('Failed to fetch current user:', error);
      return null;
    }
  }

  /**
   * Check if user is authenticated
   */
  async isAuthenticated(): Promise<boolean> {
    try {
      await Auth.currentAuthenticatedUser();
      return true;
    } catch {
      return false;
    }
  }
  
  /**
   * Check if user is authenticated (sync version using stored token)
   */
  isAuthenticatedSync(): boolean {
    return !!this.getStoredToken() && !this.isTokenExpired();
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

// Re-export verification functions on the authService instance
authService.verifyEmail = verifyEmail;
authService.resendVerificationCode = resendVerificationCode;

// Additional methods for email verification
export interface VerifyEmailCredentials {
  email: string;
  code: string;
}

/**
 * Verify email with confirmation code
 */
export async function verifyEmail(credentials: VerifyEmailCredentials): Promise<void> {
  try {
    await Auth.confirmSignUp(credentials.email, credentials.code);
  } catch (error: any) {
    console.error('Email verification failed:', error);
    
    if (error.code === 'CodeMismatchException') {
      throw new Error('Invalid verification code.');
    } else if (error.code === 'ExpiredCodeException') {
      throw new Error('Verification code has expired. Please request a new one.');
    }
    
    throw new Error(error.message || 'Verification failed.');
  }
}

/**
 * Resend verification code
 */
export async function resendVerificationCode(email: string): Promise<void> {
  try {
    await Auth.resendSignUp(email);
  } catch (error: any) {
    console.error('Failed to resend verification code:', error);
    throw new Error(error.message || 'Failed to resend code.');
  }
}

// Setup token refresh on initialization
authService.setupTokenRefresh();

export default authService;