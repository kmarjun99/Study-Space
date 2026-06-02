"""
Security utilities for password validation and sanitization
"""
import re
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return pwd_context.verify(plain_password, hashed_password)


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
    common_passwords = ['password', '12345678', 'qwerty', 'admin', 'letmein', 'welcome']
    if password.lower() in common_passwords:
        return False, "Password is too common. Please choose a stronger password"
    
    return True, ""


def sanitize_html(text: str) -> str:
    """Remove HTML tags and dangerous content from text"""
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Remove javascript: protocol
    text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)
    
    # Remove event handlers
    text = re.sub(r'on\w+\s*=', '', text, flags=re.IGNORECASE)
    
    return text.strip()


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal attacks"""
    # Remove path components
    filename = filename.split("/")[-1].split("\\")[-1]
    
    # Remove dangerous characters
    filename = re.sub(r'[^\w\s\-\.]', '', filename)
    
    # Limit length
    if len(filename) > 255:
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        filename = name[:250] + ('.' + ext if ext else '')
    
    return filename


def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_phone(phone: str) -> bool:
    """Validate Indian phone number"""
    pattern = r'^[6-9]\d{9}$'
    return bool(re.match(pattern, phone))
