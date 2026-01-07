"""
Token Service
Handles OAuth token encryption, storage, and refresh
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import get_settings
from app.models.user import User

settings = get_settings()
logger = logging.getLogger(__name__)


class TokenService:
    """
    Service for managing OAuth tokens securely.
    Tokens are encrypted at rest using Fernet symmetric encryption.
    """
    
    def __init__(self):
        """Initialize with Fernet key from settings"""
        try:
            self._fernet = Fernet(settings.FERNET_KEY.encode())
        except Exception as e:
            logger.error(f"Failed to initialize Fernet: {e}")
            raise ValueError(
                "Invalid FERNET_KEY. Generate with: "
                "python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            )
    
    def encrypt_token(self, token: str) -> str:
        """
        Encrypt a token for secure storage.
        
        Args:
            token: Plaintext token to encrypt
            
        Returns:
            Base64-encoded encrypted token
        """
        if not token:
            return ""
        
        encrypted = self._fernet.encrypt(token.encode())
        return encrypted.decode()
    
    def decrypt_token(self, encrypted_token: str) -> Optional[str]:
        """
        Decrypt an encrypted token.
        
        Args:
            encrypted_token: Base64-encoded encrypted token
            
        Returns:
            Decrypted plaintext token, or None if decryption fails
        """
        if not encrypted_token:
            return None
        
        try:
            decrypted = self._fernet.decrypt(encrypted_token.encode())
            return decrypted.decode()
        except InvalidToken:
            logger.error("Failed to decrypt token - invalid or corrupted")
            return None
        except Exception as e:
            logger.error(f"Token decryption error: {e}")
            return None
    
    async def store_oauth_tokens(
        self,
        db: AsyncSession,
        user: User,
        access_token: str,
        refresh_token: str,
        expires_in: int
    ) -> User:
        """
        Encrypt and store OAuth tokens for a user.
        
        Args:
            db: Database session
            user: User model instance
            access_token: OAuth access token
            refresh_token: OAuth refresh token
            expires_in: Token lifetime in seconds
            
        Returns:
            Updated user instance
        """
        # Encrypt tokens
        user.encrypted_access_token = self.encrypt_token(access_token)
        user.encrypted_refresh_token = self.encrypt_token(refresh_token)
        
        # Calculate expiration time
        user.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        logger.info(f"Stored OAuth tokens for user {user.id}")
        return user
    
    async def get_valid_access_token(
        self,
        db: AsyncSession,
        user: User
    ) -> Optional[str]:
        """
        Get a valid access token, refreshing if necessary.
        
        Args:
            db: Database session
            user: User model instance
            
        Returns:
            Valid access token, or None if refresh fails
        """
        # Check if token needs refresh (with buffer)
        buffer = timedelta(seconds=settings.TOKEN_REFRESH_BUFFER_SECONDS)
        now = datetime.now(timezone.utc)
        
        if user.token_expires_at and (user.token_expires_at - buffer) > now:
            # Token is still valid
            return self.decrypt_token(user.encrypted_access_token)
        
        # Token expired or expiring soon - refresh it
        logger.info(f"Access token expired for user {user.id}, refreshing...")
        
        refresh_token = self.decrypt_token(user.encrypted_refresh_token)
        if not refresh_token:
            logger.error(f"No refresh token available for user {user.id}")
            return None
        
        # Refresh the token
        new_tokens = await self.refresh_google_token(refresh_token)
        if not new_tokens:
            logger.error(f"Token refresh failed for user {user.id}")
            return None
        
        # Store new tokens
        await self.store_oauth_tokens(
            db=db,
            user=user,
            access_token=new_tokens[0],
            refresh_token=new_tokens[1] or refresh_token,  # Keep old refresh if not provided
            expires_in=new_tokens[2]
        )
        
        return new_tokens[0]
    
    async def refresh_google_token(
        self,
        refresh_token: str
    ) -> Optional[Tuple[str, Optional[str], int]]:
        """
        Refresh a Google OAuth token.
        
        Args:
            refresh_token: Current refresh token
            
        Returns:
            Tuple of (access_token, new_refresh_token, expires_in) or None
        """
        import aiohttp
        
        token_url = "https://oauth2.googleapis.com/token"
        
        data = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(token_url, data=data) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Token refresh failed: {error_text}")
                        return None
                    
                    token_data = await response.json()
                    
                    return (
                        token_data["access_token"],
                        token_data.get("refresh_token"),  # May not be included
                        token_data.get("expires_in", 3600)
                    )
                    
        except Exception as e:
            logger.error(f"Token refresh request failed: {e}")
            return None
    
    async def revoke_tokens(self, db: AsyncSession, user: User) -> bool:
        """
        Revoke and clear OAuth tokens for a user.
        
        Args:
            db: Database session
            user: User model instance
            
        Returns:
            True if successful
        """
        import aiohttp
        
        # Revoke at Google
        access_token = self.decrypt_token(user.encrypted_access_token)
        if access_token:
            try:
                revoke_url = f"https://oauth2.googleapis.com/revoke?token={access_token}"
                async with aiohttp.ClientSession() as session:
                    async with session.post(revoke_url) as response:
                        if response.status == 200:
                            logger.info(f"Revoked Google token for user {user.id}")
                        else:
                            logger.warning(f"Token revocation returned {response.status}")
            except Exception as e:
                logger.error(f"Failed to revoke Google token: {e}")
        
        # Clear stored tokens
        user.encrypted_access_token = None
        user.encrypted_refresh_token = None
        user.token_expires_at = None
        
        db.add(user)
        await db.commit()
        
        logger.info(f"Cleared OAuth tokens for user {user.id}")
        return True


# Singleton instance
_token_service: Optional[TokenService] = None


def get_token_service() -> TokenService:
    """Get or create TokenService singleton"""
    global _token_service
    if _token_service is None:
        _token_service = TokenService()
    return _token_service
