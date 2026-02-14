"""
Security Middleware for SSPACE Application
Implements various security measures including rate limiting, security headers, and input validation
"""

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from typing import Callable
import time
from collections import defaultdict
import re
import logging

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adds security headers to all responses
    """
    async def dispatch(self, request: Request, call_next: Callable):
        response = await call_next(request)
        
        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        
        # Prevent MIME sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # XSS Protection
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Strict Transport Security (HTTPS only)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        # Content Security Policy
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' https://maps.googleapis.com https://maps.gstatic.com; "
            "frame-ancestors 'none';"
        )
        
        # Referrer Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Permissions Policy
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=()"
        )
        
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware to prevent abuse
    """
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests = defaultdict(list)
        
    async def dispatch(self, request: Request, call_next: Callable):
        # Get client IP
        client_ip = request.client.host
        
        # Special rate limits for sensitive endpoints
        if request.url.path.startswith("/api/auth/login"):
            limit = 5  # Only 5 login attempts per minute
        elif request.url.path.startswith("/api/auth/register"):
            limit = 3  # Only 3 registration attempts per minute
        else:
            limit = self.requests_per_minute
        
        current_time = time.time()
        
        # Clean old requests (older than 1 minute)
        self.requests[client_ip] = [
            req_time for req_time in self.requests[client_ip]
            if current_time - req_time < 60
        ]
        
        # Check rate limit
        if len(self.requests[client_ip]) >= limit:
            logger.warning(f"Rate limit exceeded for IP: {client_ip} on {request.url.path}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Too many requests. Please try again later.",
                    "retry_after": 60
                }
            )
        
        # Add current request
        self.requests[client_ip].append(current_time)
        
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(limit - len(self.requests[client_ip]))
        response.headers["X-RateLimit-Reset"] = str(int(current_time + 60))
        
        return response


class InputValidationMiddleware(BaseHTTPMiddleware):
    """
    Validates and sanitizes input to prevent injection attacks
    """
    
    # Suspicious patterns that might indicate attacks
    SUSPICIOUS_PATTERNS = [
        r"<script[\s\S]*?>[\s\S]*?</script>",  # XSS
        r"javascript:",  # XSS
        r"on\w+\s*=",  # Event handlers
        r"(\bUNION\b|\bSELECT\b|\bINSERT\b|\bUPDATE\b|\bDELETE\b|\bDROP\b)",  # SQL injection
        r"\.\.\/",  # Path traversal
        r"\$\{",  # Template injection
    ]
    
    async def dispatch(self, request: Request, call_next: Callable):
        # Skip validation for certain paths
        if request.url.path.startswith("/docs") or request.url.path.startswith("/openapi"):
            return await call_next(request)
        
        # Check query parameters
        for key, value in request.query_params.items():
            if self._contains_suspicious_content(value):
                logger.warning(f"Suspicious query parameter detected: {key}={value} from {request.client.host}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid input detected"
                )
        
        # Check path parameters
        if self._contains_suspicious_content(request.url.path):
            logger.warning(f"Suspicious path detected: {request.url.path} from {request.client.host}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid request path"
            )
        
        return await call_next(request)
    
    def _contains_suspicious_content(self, text: str) -> bool:
        """Check if text contains suspicious patterns"""
        for pattern in self.SUSPICIOUS_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False


class IPWhitelistMiddleware(BaseHTTPMiddleware):
    """
    Restricts admin endpoints to whitelisted IPs
    """
    def __init__(self, app, whitelist: list = None):
        super().__init__(app)
        self.whitelist = whitelist or ["127.0.0.1", "::1"]
    
    async def dispatch(self, request: Request, call_next: Callable):
        # Only check admin routes
        if request.url.path.startswith("/api/admin") or request.url.path.startswith("/api/super-admin"):
            client_ip = request.client.host
            
            if client_ip not in self.whitelist:
                logger.warning(f"Unauthorized admin access attempt from IP: {client_ip}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied from your IP address"
                )
        
        return await call_next(request)


def setup_cors(app, allowed_origins: list):
    """
    Configure CORS with security best practices
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        allow_headers=["*"],
        expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
        max_age=3600,  # Cache preflight requests for 1 hour
    )


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal attacks
    """
    # Remove path components
    filename = filename.split("/")[-1].split("\\")[-1]
    
    # Remove dangerous characters
    filename = re.sub(r'[^\w\s\-\.]', '', filename)
    
    # Limit length
    if len(filename) > 255:
        name, ext = filename.rsplit('.', 1)
        filename = name[:250] + '.' + ext
    
    return filename


def validate_file_upload(file_content: bytes, allowed_extensions: list, max_size: int) -> tuple[bool, str]:
    """
    Validate uploaded file
    Returns: (is_valid, error_message)
    """
    # Check file size
    if len(file_content) > max_size:
        return False, f"File size exceeds maximum allowed size of {max_size / 1024 / 1024}MB"
    
    # Check for executable content (basic check)
    dangerous_signatures = [
        b'MZ',  # Windows executable
        b'\x7fELF',  # Linux executable
        b'#!',  # Script with shebang
    ]
    
    for signature in dangerous_signatures:
        if file_content.startswith(signature):
            return False, "File type not allowed"
    
    return True, ""


def hash_password(password: str) -> str:
    """
    Hash password using bcrypt (implemented in security.py already)
    """
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return pwd_context.hash(password)


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Validate password meets security requirements
    Returns: (is_valid, error_message)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    
    if not re.search(r'\d', password):
        return False, "Password must contain at least one number"
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character"
    
    # Check for common weak passwords
    common_passwords = ['password', '12345678', 'qwerty', 'admin', 'letmein']
    if password.lower() in common_passwords:
        return False, "Password is too common. Please choose a stronger password"
    
    return True, ""


def sanitize_html(text: str) -> str:
    """
    Remove HTML tags and dangerous content from text
    """
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Remove javascript: protocol
    text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)
    
    # Remove event handlers
    text = re.sub(r'on\w+\s*=', '', text, flags=re.IGNORECASE)
    
    return text.strip()
