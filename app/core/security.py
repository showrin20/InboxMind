"""
Enterprise Security Module
Token encryption, OAuth token management, and security utilities
"""
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from jose import JWTError, jwt
from passlib.context import CryptContext
import secrets
import hashlib
import logging

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Fernet encryption for OAuth tokens
try:
    fernet = Fernet(settings.FERNET_KEY.encode() if isinstance(settings.FERNET_KEY, str) else settings.FERNET_KEY)
except Exception as e:
    logger.critical(f"Failed to initialize Fernet encryption: {e}")
    raise ValueError("Invalid FERNET_KEY. Generate with: Fernet.generate_key()")


class TokenEncryption:
    """
    Handles encryption/decryption of OAuth tokens at rest.
    SECURITY RULE: OAuth tokens must never be stored in plaintext.
    """
    
    @staticmethod
    def encrypt_token(token: str) -> str:
        """
        Encrypt an OAuth token for storage.
        
        Args:
            token: Plain OAuth access/refresh token
            
        Returns:
            Encrypted token as base64 string
        """
        if not token:
            raise ValueError("Cannot encrypt empty token")
        
        try:
            encrypted = fernet.encrypt(token.encode())
            # Never log the actual token
            logger.debug(f"Token encrypted successfully (length: {len(token)})")
            return encrypted.decode()
        except Exception as e:
            logger.error(f"Token encryption failed: {type(e).__name__}")
            raise
    
    @staticmethod
    def decrypt_token(encrypted_token: str) -> str:
        """
        Decrypt an OAuth token from storage.
        
        Args:
            encrypted_token: Encrypted token from database
            
        Returns:
            Decrypted plaintext token
        """
        if not encrypted_token:
            raise ValueError("Cannot decrypt empty token")
        
        try:
            decrypted = fernet.decrypt(encrypted_token.encode())
            logger.debug("Token decrypted successfully")
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Token decryption failed: {type(e).__name__}")
            raise ValueError("Invalid or corrupted encrypted token")
    
    @staticmethod
    def hash_token_for_lookup(token: str) -> str:
        """
        Create a hash of the token for revocation lookups without storing plaintext.
        Uses SHA-256 for fast, deterministic hashing.
        """
        return hashlib.sha256(token.encode()).hexdigest()


class JWTManager:
    """
    JWT token management for API authentication.
    Separate from OAuth tokens - these are for our API access.
    """
    
    @staticmethod
    def create_access_token(
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create a JWT access token for API authentication.
        
        Args:
            data: Payload to encode (should include user_id, org_id)
            expires_delta: Optional custom expiration time
            
        Returns:
            Encoded JWT token
        """
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(
                minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
            )
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        })
        
        # Ensure tenant isolation in JWT
        if "org_id" not in to_encode or "user_id" not in to_encode:
            logger.warning("JWT created without tenant identifiers")
        
        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
        
        logger.info(f"JWT created for user_id={to_encode.get('user_id')}, org_id={to_encode.get('org_id')}")
        return encoded_jwt
    
    @staticmethod
    def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
        """
        Decode and validate JWT access token.
        
        Args:
            token: JWT token from request
            
        Returns:
            Decoded payload or None if invalid
        """
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )
            
            # Validate token type
            if payload.get("type") != "access":
                logger.warning("Invalid token type")
                return None
            
            # Ensure tenant identifiers present
            if "user_id" not in payload or "org_id" not in payload:
                logger.error("JWT missing tenant identifiers")
                return None
            
            return payload
            
        except JWTError as e:
            logger.warning(f"JWT decode failed: {type(e).__name__}")
            return None
    
    @staticmethod
    def verify_token_not_expired(payload: Dict[str, Any]) -> bool:
        """Check if token is expired"""
        exp = payload.get("exp")
        if not exp:
            return False
        return datetime.fromtimestamp(exp) > datetime.utcnow()


class PasswordManager:
    """Password hashing and verification"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt"""
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)


class SecurityUtils:
    """Additional security utilities"""
    
    @staticmethod
    def generate_state_token() -> str:
        """
        Generate a cryptographically secure state token for OAuth flows.
        Prevents CSRF attacks during OAuth callback.
        """
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def generate_api_key() -> str:
        """Generate a secure API key"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def sanitize_for_logging(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove sensitive fields from data before logging.
        SECURITY RULE: Never log tokens, keys, or passwords.
        """
        sensitive_fields = {
            "token", "access_token", "refresh_token", "password",
            "secret", "api_key", "client_secret", "fernet_key"
        }
        
        sanitized = {}
        for key, value in data.items():
            if any(field in key.lower() for field in sensitive_fields):
                sanitized[key] = "***REDACTED***"
            elif isinstance(value, dict):
                sanitized[key] = SecurityUtils.sanitize_for_logging(value)
            else:
                sanitized[key] = value
        
        return sanitized
    
    @staticmethod
    def validate_tenant_access(
        user_org_id: str,
        resource_org_id: str,
        user_id: Optional[str] = None,
        resource_user_id: Optional[str] = None
    ) -> bool:
        """
        Validate tenant isolation for resource access.
        Users can only access resources within their org.
        
        Args:
            user_org_id: Organization ID from JWT
            resource_org_id: Organization ID of requested resource
            user_id: Optional user ID for user-level resources
            resource_user_id: Optional owner user ID of resource
            
        Returns:
            True if access allowed, False otherwise
        """
        # Organization must match
        if user_org_id != resource_org_id:
            logger.warning(
                f"Tenant isolation violation attempt: "
                f"user_org={user_org_id}, resource_org={resource_org_id}"
            )
            return False
        
        # If user-level resource, user must match
        if resource_user_id and user_id and user_id != resource_user_id:
            logger.warning(
                f"User isolation violation attempt: "
                f"user={user_id}, resource_user={resource_user_id}"
            )
            return False
        
        return True


# Export instances
token_encryption = TokenEncryption()
jwt_manager = JWTManager()
password_manager = PasswordManager()
security_utils = SecurityUtils()


# Convenience functions
def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT access token.
    
    Wrapper around JWTManager.create_access_token for easier imports.
    """
    return jwt_manager.create_access_token(data, expires_delta)


async def get_current_user_id(request: "Request") -> str:
    """
    Extract and validate user ID from request JWT.
    
    Args:
        request: FastAPI Request object
        
    Returns:
        User ID string
        
    Raises:
        HTTPException: If token is invalid or missing
    """
    from fastapi import HTTPException, status
    
    # Get token from Authorization header
    auth_header = request.headers.get("Authorization")
    
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    token = auth_header[7:]  # Remove "Bearer " prefix
    
    # Decode and validate token
    payload = jwt_manager.decode_access_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    user_id = payload.get("sub")  # Standard JWT subject claim
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    return user_id


async def get_current_user(
    request: "Request",
    db: "AsyncSession"
) -> "User":
    """
    Get the current authenticated user from request.
    
    Args:
        request: FastAPI Request object
        db: Database session
        
    Returns:
        User model instance
        
    Raises:
        HTTPException: If user not found or inactive
    """
    from fastapi import HTTPException, status
    from sqlalchemy import select
    from app.models.user import User
    
    user_id = await get_current_user_id(request)
    
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    return user
