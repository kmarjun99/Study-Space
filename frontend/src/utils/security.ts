// Security utilities for React frontend
import DOMPurify from 'dompurify';

/**
 * Sanitize HTML content to prevent XSS attacks
 */
export const sanitizeHTML = (dirty: string): string => {
  return DOMPurify.sanitize(dirty, {
    ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'a', 'p', 'br'],
    ALLOWED_ATTR: ['href', 'target']
  });
};

/**
 * Validate email format
 */
export const validateEmail = (email: string): boolean => {
  const pattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return pattern.test(email);
};

/**
 * Validate password strength
 */
export const validatePassword = (password: string): { 
  isValid: boolean; 
  errors: string[] 
} => {
  const errors: string[] = [];
  
  if (password.length < 8) {
    errors.push('Password must be at least 8 characters long');
  }
  
  if (!/[A-Z]/.test(password)) {
    errors.push('Password must contain at least one uppercase letter');
  }
  
  if (!/[a-z]/.test(password)) {
    errors.push('Password must contain at least one lowercase letter');
  }
  
  if (!/\d/.test(password)) {
    errors.push('Password must contain at least one number');
  }
  
  if (!/[!@#$%^&*(),.?":{}|<>]/.test(password)) {
    errors.push('Password must contain at least one special character');
  }
  
  return {
    isValid: errors.length === 0,
    errors
  };
};

/**
 * Validate phone number (Indian format)
 */
export const validatePhone = (phone: string): boolean => {
  const pattern = /^[6-9]\d{9}$/;
  return pattern.test(phone);
};

/**
 * Sanitize user input for search/filter
 */
export const sanitizeInput = (input: string): string => {
  return input
    .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
    .replace(/javascript:/gi, '')
    .replace(/on\w+\s*=/gi, '')
    .trim();
};

/**
 * Check if URL is safe (prevent open redirect attacks)
 */
export const isSafeURL = (url: string): boolean => {
  try {
    const parsed = new URL(url, window.location.origin);
    return parsed.origin === window.location.origin;
  } catch {
    return false;
  }
};

/**
 * Generate CSRF token (store in sessionStorage)
 */
export const generateCSRFToken = (): string => {
  const token = Array.from(crypto.getRandomValues(new Uint8Array(32)))
    .map(b => b.toString(16).padStart(2, '0'))
    .join('');
  sessionStorage.setItem('csrf_token', token);
  return token;
};

/**
 * Get CSRF token for requests
 */
export const getCSRFToken = (): string | null => {
  return sessionStorage.getItem('csrf_token');
};

/**
 * Secure token storage (use httpOnly cookies in production)
 */
export const secureTokenStorage = {
  /**
   * Store token securely
   * NOTE: In production, use httpOnly cookies set by backend
   */
  setToken: (token: string) => {
    // For development only - use httpOnly cookies in production
    sessionStorage.setItem('studySpace_token', token);
  },
  
  /**
   * Get token
   */
  getToken: (): string | null => {
    return sessionStorage.getItem('studySpace_token');
  },
  
  /**
   * Remove token
   */
  removeToken: () => {
    sessionStorage.removeItem('studySpace_token');
    sessionStorage.removeItem('csrf_token');
  }
};

/**
 * Rate limit client-side requests
 */
export class ClientRateLimiter {
  private requests: Map<string, number[]> = new Map();
  private limit: number;
  private windowMs: number;

  constructor(limit: number = 60, windowMs: number = 60000) {
    this.limit = limit;
    this.windowMs = windowMs;
  }

  canMakeRequest(key: string): boolean {
    const now = Date.now();
    const requests = this.requests.get(key) || [];
    
    // Remove old requests outside window
    const validRequests = requests.filter(time => now - time < this.windowMs);
    
    if (validRequests.length >= this.limit) {
      return false;
    }
    
    validRequests.push(now);
    this.requests.set(key, validRequests);
    return true;
  }
}

/**
 * Detect and prevent XSS in user input
 */
export const detectXSS = (input: string): boolean => {
  const xssPatterns = [
    /<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi,
    /javascript:/gi,
    /on\w+\s*=/gi,
    /<iframe/gi,
    /<object/gi,
    /<embed/gi
  ];
  
  return xssPatterns.some(pattern => pattern.test(input));
};

/**
 * Format file size
 */
export const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
};

/**
 * Validate file upload
 */
export const validateFile = (
  file: File,
  options: {
    maxSize?: number; // in bytes
    allowedTypes?: string[];
  }
): { isValid: boolean; error?: string } => {
  const maxSize = options.maxSize || 5 * 1024 * 1024; // 5MB default
  const allowedTypes = options.allowedTypes || ['image/jpeg', 'image/png', 'image/jpg', 'application/pdf'];
  
  if (file.size > maxSize) {
    return {
      isValid: false,
      error: `File size must be less than ${formatFileSize(maxSize)}`
    };
  }
  
  if (!allowedTypes.includes(file.type)) {
    return {
      isValid: false,
      error: `File type not allowed. Allowed types: ${allowedTypes.join(', ')}`
    };
  }
  
  return { isValid: true };
};

/**
 * Content Security Policy violation reporter
 */
export const reportCSPViolation = (violationEvent: SecurityPolicyViolationEvent) => {
  console.error('CSP Violation:', {
    documentURI: violationEvent.documentURI,
    violatedDirective: violationEvent.violatedDirective,
    effectiveDirective: violationEvent.effectiveDirective,
    originalPolicy: violationEvent.originalPolicy,
    blockedURI: violationEvent.blockedURI,
    statusCode: violationEvent.statusCode
  });
  
  // Send to backend for logging
  // fetch('/api/security/csp-report', {
  //   method: 'POST',
  //   body: JSON.stringify({ violation: violationEvent })
  // });
};

// Add CSP violation listener
if (typeof window !== 'undefined') {
  document.addEventListener('securitypolicyviolation', reportCSPViolation);
}
