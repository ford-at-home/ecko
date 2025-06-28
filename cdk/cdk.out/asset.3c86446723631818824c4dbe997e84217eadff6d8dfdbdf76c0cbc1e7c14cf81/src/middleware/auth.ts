import { Request, Response, NextFunction } from 'express';
import { CognitoJwtVerifier } from 'aws-jwt-verify';
import { CognitoIdTokenPayload, CognitoAccessTokenPayload } from 'aws-jwt-verify/jwt-model';

// Environment configuration
const USER_POOL_ID = process.env.COGNITO_USER_POOL_ID!;
const CLIENT_ID = process.env.COGNITO_CLIENT_ID!;
const AWS_REGION = process.env.AWS_REGION || 'us-east-1';

if (!USER_POOL_ID || !CLIENT_ID) {
  throw new Error('Missing required Cognito configuration. Please set COGNITO_USER_POOL_ID and COGNITO_CLIENT_ID environment variables.');
}

// Create JWT verifiers for different token types
const idTokenVerifier = CognitoJwtVerifier.create({
  userPoolId: USER_POOL_ID,
  tokenUse: 'id',
  clientId: CLIENT_ID,
});

const accessTokenVerifier = CognitoJwtVerifier.create({
  userPoolId: USER_POOL_ID,
  tokenUse: 'access',
  clientId: CLIENT_ID,
});

// Extended Request interface to include user information
export interface AuthenticatedRequest extends Request {
  user?: {
    sub: string;
    username: string;
    email: string;
    email_verified: boolean;
    given_name?: string;
    family_name?: string;
    token_use: 'id' | 'access';
    aud: string;
    iss: string;
    exp: number;
    iat: number;
    auth_time?: number;
    [key: string]: any;
  };
}

/**
 * Extract JWT token from Authorization header
 */
function extractToken(authHeader: string | undefined): string | null {
  if (!authHeader) {
    return null;
  }

  // Support both "Bearer token" and "token" formats
  const token = authHeader.startsWith('Bearer ') 
    ? authHeader.slice(7) 
    : authHeader;

  return token || null;
}

/**
 * Middleware to authenticate requests using Cognito JWT tokens
 * Supports both ID tokens and Access tokens
 */
export const authenticateToken = async (
  req: AuthenticatedRequest,
  res: Response,
  next: NextFunction
): Promise<void> => {
  try {
    const token = extractToken(req.headers.authorization);

    if (!token) {
      res.status(401).json({
        error: 'Authentication required',
        message: 'No token provided in Authorization header',
      });
      return;
    }

    let payload: CognitoIdTokenPayload | CognitoAccessTokenPayload;
    let tokenType: 'id' | 'access';

    try {
      // Try to verify as ID token first (contains user info)
      payload = await idTokenVerifier.verify(token);
      tokenType = 'id';
    } catch (idTokenError) {
      try {
        // If ID token verification fails, try as Access token
        payload = await accessTokenVerifier.verify(token);
        tokenType = 'access';
      } catch (accessTokenError) {
        console.error('Token verification failed:', { idTokenError, accessTokenError });
        res.status(401).json({
          error: 'Invalid token',
          message: 'Token verification failed',
        });
        return;
      }
    }

    // Extract user information from token
    req.user = {
      sub: payload.sub,
      username: payload.username || payload.sub,
      email: (payload as CognitoIdTokenPayload).email || '',
      email_verified: (payload as CognitoIdTokenPayload).email_verified || false,
      given_name: (payload as CognitoIdTokenPayload).given_name,
      family_name: (payload as CognitoIdTokenPayload).family_name,
      token_use: tokenType,
      aud: payload.aud,
      iss: payload.iss,
      exp: payload.exp,
      iat: payload.iat,
      auth_time: (payload as CognitoIdTokenPayload).auth_time,
      ...payload, // Include any additional custom attributes
    };

    next();
  } catch (error) {
    console.error('Authentication middleware error:', error);
    res.status(500).json({
      error: 'Authentication error',
      message: 'Internal server error during authentication',
    });
  }
};

/**
 * Middleware to optionally authenticate requests
 * Sets req.user if token is valid, but doesn't reject if missing/invalid
 */
export const optionalAuth = async (
  req: AuthenticatedRequest,
  res: Response,
  next: NextFunction
): Promise<void> => {
  try {
    const token = extractToken(req.headers.authorization);

    if (!token) {
      next();
      return;
    }

    let payload: CognitoIdTokenPayload | CognitoAccessTokenPayload;
    let tokenType: 'id' | 'access';

    try {
      payload = await idTokenVerifier.verify(token);
      tokenType = 'id';
    } catch (idTokenError) {
      try {
        payload = await accessTokenVerifier.verify(token);
        tokenType = 'access';
      } catch (accessTokenError) {
        // Invalid token, but that's okay for optional auth
        next();
        return;
      }
    }

    req.user = {
      sub: payload.sub,
      username: payload.username || payload.sub,
      email: (payload as CognitoIdTokenPayload).email || '',
      email_verified: (payload as CognitoIdTokenPayload).email_verified || false,
      given_name: (payload as CognitoIdTokenPayload).given_name,
      family_name: (payload as CognitoIdTokenPayload).family_name,
      token_use: tokenType,
      aud: payload.aud,
      iss: payload.iss,
      exp: payload.exp,
      iat: payload.iat,
      auth_time: (payload as CognitoIdTokenPayload).auth_time,
      ...payload,
    };

    next();
  } catch (error) {
    console.error('Optional auth middleware error:', error);
    // For optional auth, continue even if there's an error
    next();
  }
};

/**
 * Middleware to require specific user attributes
 */
export const requireEmailVerified = (
  req: AuthenticatedRequest,
  res: Response,
  next: NextFunction
): void => {
  if (!req.user) {
    res.status(401).json({
      error: 'Authentication required',
      message: 'User not authenticated',
    });
    return;
  }

  if (!req.user.email_verified) {
    res.status(403).json({
      error: 'Email verification required',
      message: 'Please verify your email address before accessing this resource',
    });
    return;
  }

  next();
};

/**
 * Middleware to require ID token (contains user profile information)
 */
export const requireIdToken = (
  req: AuthenticatedRequest,
  res: Response,
  next: NextFunction
): void => {
  if (!req.user) {
    res.status(401).json({
      error: 'Authentication required',
      message: 'User not authenticated',
    });
    return;
  }

  if (req.user.token_use !== 'id') {
    res.status(401).json({
      error: 'ID token required',
      message: 'This endpoint requires an ID token with user profile information',
    });
    return;
  }

  next();
};

/**
 * Error handler for authentication errors
 */
export const authErrorHandler = (
  error: any,
  req: Request,
  res: Response,
  next: NextFunction
): void => {
  if (error.name === 'UnauthorizedError') {
    res.status(401).json({
      error: 'Unauthorized',
      message: error.message || 'Invalid token',
    });
    return;
  }

  next(error);
};