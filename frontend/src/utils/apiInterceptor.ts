/**
 * API Interceptor Configuration
 * Handles automatic token refresh and error handling
 */

import { authService } from '../services/authService';
import { apiClient } from './apiClient';

class ApiInterceptor {
  private isRefreshing = false;
  private refreshPromise: Promise<any> | null = null;

  /**
   * Setup API interceptors
   */
  setup(): void {
    // Handle 401 errors with automatic token refresh
    this.setupErrorInterceptor();
    
    // Setup request interceptor to always use latest token
    this.setupRequestInterceptor();
  }

  /**
   * Setup request interceptor
   */
  private setupRequestInterceptor(): void {
    // Before each request, ensure we have the latest token
    const originalRequest = apiClient.request.bind(apiClient);
    
    apiClient.request = async function(endpoint: string, options: any = {}) {
      // Check if token is expired before making request
      if (authService.isAuthenticated() && authService.isTokenExpired()) {
        await authService.refreshToken();
      }
      
      // Ensure latest token is set
      const token = authService.getStoredToken();
      if (token) {
        apiClient.setAuthToken(token);
      }
      
      return originalRequest(endpoint, options);
    };
  }

  /**
   * Setup error interceptor
   */
  private setupErrorInterceptor(): void {
    // Wrap the original request method
    const originalRequest = apiClient.request.bind(apiClient);
    const interceptor = this;
    
    apiClient.request = async function(endpoint: string, options: any = {}) {
      try {
        return await originalRequest(endpoint, options);
      } catch (error: any) {
        // Handle authentication errors
        if (error.statusCode === 401 && authService.isAuthenticated()) {
          // Try to refresh the token
          if (!interceptor.isRefreshing) {
            interceptor.isRefreshing = true;
            interceptor.refreshPromise = authService.refreshToken()
              .then((tokens) => {
                interceptor.isRefreshing = false;
                interceptor.refreshPromise = null;
                return tokens;
              })
              .catch((refreshError) => {
                interceptor.isRefreshing = false;
                interceptor.refreshPromise = null;
                // Refresh failed, logout user
                authService.logout();
                window.location.href = '/login';
                throw refreshError;
              });
          }
          
          // Wait for refresh to complete
          if (interceptor.refreshPromise) {
            await interceptor.refreshPromise;
            
            // Retry the original request with new token
            const newToken = authService.getStoredToken();
            if (newToken) {
              apiClient.setAuthToken(newToken);
              return await originalRequest(endpoint, options);
            }
          }
        }
        
        // Handle other errors
        if (error.statusCode === 403) {
          console.error('Access forbidden:', error);
          // Could redirect to an error page or show a notification
        }
        
        if (error.statusCode === 500) {
          console.error('Server error:', error);
          // Could show a user-friendly error message
        }
        
        // Re-throw the error for the calling code to handle
        throw error;
      }
    };
  }
}

// Create and export singleton instance
export const apiInterceptor = new ApiInterceptor();

// Auto-setup on import
apiInterceptor.setup();

export default apiInterceptor;