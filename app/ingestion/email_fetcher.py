"""
Email Fetcher
Fetches emails from Gmail using the Gmail API
"""
import logging
from datetime import datetime, timezone
from typing import Optional, List, AsyncGenerator, Dict, Any
from dataclasses import dataclass

from app.core.config import get_settings
from app.ingestion.email_parser import EmailParser, ParsedEmail, get_email_parser

settings = get_settings()
logger = logging.getLogger(__name__)


@dataclass
class FetchResult:
    """Result of email fetch operation"""
    emails: List[ParsedEmail]
    next_page_token: Optional[str] = None
    total_fetched: int = 0
    errors: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class GmailFetcher:
    """
    Fetches emails from Gmail using the Gmail API.
    
    Uses OAuth2 access tokens to authenticate.
    Supports incremental sync using history ID.
    """
    
    BASE_URL = "https://gmail.googleapis.com/gmail/v1/users/me"
    
    def __init__(self, access_token: str):
        """
        Initialize fetcher with OAuth access token.
        
        Args:
            access_token: Valid Google OAuth access token with Gmail scope
        """
        self._access_token = access_token
        self._parser = get_email_parser()
        self._headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
    
    async def fetch_emails(
        self,
        max_results: int = 100,
        page_token: Optional[str] = None,
        query: Optional[str] = None,
        label_ids: Optional[List[str]] = None,
        include_spam_trash: bool = False
    ) -> FetchResult:
        """
        Fetch emails from Gmail.
        
        Args:
            max_results: Maximum number of emails to fetch (max 500)
            page_token: Token for pagination
            query: Gmail search query (e.g., "after:2024/01/01")
            label_ids: Filter by label IDs (e.g., ["INBOX"])
            include_spam_trash: Include spam and trash folders
            
        Returns:
            FetchResult with parsed emails and pagination info
        """
        import aiohttp
        
        # Build query parameters
        params = {
            "maxResults": min(max_results, 500)
        }
        
        if page_token:
            params["pageToken"] = page_token
        
        if query:
            params["q"] = query
        
        if label_ids:
            params["labelIds"] = label_ids
        
        if include_spam_trash:
            params["includeSpamTrash"] = "true"
        
        try:
            async with aiohttp.ClientSession() as session:
                # List messages
                list_url = f"{self.BASE_URL}/messages"
                async with session.get(list_url, headers=self._headers, params=params) as response:
                    if response.status == 401:
                        error_msg = "Access token expired or invalid"
                        print(f"\n[EMAIL FETCH ERROR] {error_msg}")
                        raise AuthenticationError(error_msg)
                    
                    if response.status != 200:
                        error_text = await response.text()
                        error_msg = f"Gmail API error: {response.status} - {error_text}"
                        logger.error(error_msg)
                        print(f"\n[EMAIL FETCH ERROR] {error_msg}")
                        raise GmailAPIError(f"Failed to list messages: {response.status}")
                    
                    list_data = await response.json()
                
                messages = list_data.get("messages", [])
                next_page_token = list_data.get("nextPageToken")
                
                if not messages:
                    return FetchResult(
                        emails=[],
                        next_page_token=next_page_token,
                        total_fetched=0
                    )
                
                # Fetch full message content for each message
                emails = []
                errors = []
                
                for msg_stub in messages:
                    try:
                        parsed = await self._fetch_full_message(session, msg_stub["id"])
                        if parsed:
                            emails.append(parsed)
                    except Exception as e:
                        error_msg = f"Failed to fetch message {msg_stub['id']}: {e}"
                        logger.error(error_msg)
                        print(f"\n[EMAIL FETCH ERROR] {error_msg}")
                        errors.append(f"Message {msg_stub['id']}: {str(e)}")
                
                return FetchResult(
                    emails=emails,
                    next_page_token=next_page_token,
                    total_fetched=len(emails),
                    errors=errors if errors else None
                )
                
        except aiohttp.ClientError as e:
            error_msg = f"Network error fetching emails: {e}"
            logger.error(error_msg)
            print(f"\n[EMAIL FETCH ERROR] {error_msg}")
            raise GmailAPIError(f"Network error: {e}")
    
    async def _fetch_full_message(
        self,
        session: "aiohttp.ClientSession",
        message_id: str
    ) -> Optional[ParsedEmail]:
        """Fetch full message content by ID"""
        url = f"{self.BASE_URL}/messages/{message_id}"
        params = {"format": "full"}
        
        async with session.get(url, headers=self._headers, params=params) as response:
            if response.status != 200:
                logger.warning(f"Failed to fetch message {message_id}: {response.status}")
                return None
            
            msg_data = await response.json()
            return self._parser.parse_gmail_message(msg_data)
    
    async def fetch_emails_since(
        self,
        since_date: datetime,
        max_results: int = 500,
        label_ids: Optional[List[str]] = None
    ) -> AsyncGenerator[ParsedEmail, None]:
        """
        Fetch all emails since a given date.
        
        Automatically handles pagination.
        
        Args:
            since_date: Fetch emails after this date
            max_results: Maximum total emails to fetch
            label_ids: Filter by labels
            
        Yields:
            ParsedEmail objects
        """
        # Format date for Gmail query
        date_str = since_date.strftime("%Y/%m/%d")
        query = f"after:{date_str}"
        
        page_token = None
        total_fetched = 0
        
        while total_fetched < max_results:
            remaining = max_results - total_fetched
            batch_size = min(remaining, 100)
            
            result = await self.fetch_emails(
                max_results=batch_size,
                page_token=page_token,
                query=query,
                label_ids=label_ids
            )
            
            for email in result.emails:
                yield email
                total_fetched += 1
            
            if not result.next_page_token:
                break
            
            page_token = result.next_page_token
        
        logger.info(f"Fetched {total_fetched} emails since {date_str}")
    
    async def fetch_email_by_id(self, message_id: str) -> Optional[ParsedEmail]:
        """
        Fetch a specific email by its Gmail message ID.
        
        Args:
            message_id: Gmail message ID
            
        Returns:
            ParsedEmail or None if not found
        """
        import aiohttp
        
        try:
            async with aiohttp.ClientSession() as session:
                return await self._fetch_full_message(session, message_id)
        except Exception as e:
            logger.error(f"Failed to fetch email {message_id}: {e}")
            return None
    
    async def get_labels(self) -> List[Dict[str, Any]]:
        """
        Get all Gmail labels for the user.
        
        Returns:
            List of label dicts with id, name, type
        """
        import aiohttp
        
        url = f"{self.BASE_URL}/labels"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self._headers) as response:
                    if response.status != 200:
                        logger.error(f"Failed to fetch labels: {response.status}")
                        return []
                    
                    data = await response.json()
                    return data.get("labels", [])
                    
        except Exception as e:
            logger.error(f"Error fetching labels: {e}")
            return []
    
    async def get_profile(self) -> Dict[str, Any]:
        """
        Get Gmail profile info (email address, history ID).
        
        Returns:
            Profile dict with emailAddress, messagesTotal, threadsTotal, historyId
        """
        import aiohttp
        
        url = f"{self.BASE_URL}/profile"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self._headers) as response:
                    if response.status != 200:
                        logger.error(f"Failed to fetch profile: {response.status}")
                        return {}
                    
                    return await response.json()
                    
        except Exception as e:
            logger.error(f"Error fetching profile: {e}")
            return {}
    
    async def get_history(
        self,
        start_history_id: str,
        max_results: int = 100
    ) -> Dict[str, Any]:
        """
        Get mailbox history for incremental sync.
        
        Args:
            start_history_id: History ID to start from
            max_results: Maximum history records
            
        Returns:
            History data with list of changes
        """
        import aiohttp
        
        url = f"{self.BASE_URL}/history"
        params = {
            "startHistoryId": start_history_id,
            "maxResults": max_results,
            "historyTypes": ["messageAdded"]
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self._headers, params=params) as response:
                    if response.status == 404:
                        # History ID too old, need full sync
                        return {"historyId": None, "history": []}
                    
                    if response.status != 200:
                        logger.error(f"Failed to fetch history: {response.status}")
                        return {}
                    
                    return await response.json()
                    
        except Exception as e:
            logger.error(f"Error fetching history: {e}")
            return {}


class AuthenticationError(Exception):
    """Raised when OAuth token is invalid or expired"""
    pass


class GmailAPIError(Exception):
    """Raised when Gmail API returns an error"""
    pass


async def create_gmail_fetcher_for_user(
    db: "AsyncSession",
    user: "User"
) -> GmailFetcher:
    """
    Create a GmailFetcher for a user with a valid access token.
    
    Automatically refreshes token if needed.
    
    Args:
        db: Database session
        user: User model with OAuth tokens
        
    Returns:
        GmailFetcher ready to use
        
    Raises:
        AuthenticationError: If token refresh fails
    """
    from app.services.token_service import get_token_service
    from datetime import timedelta, timezone
    
    token_service = get_token_service()
    
    # Check if we have an encrypted token
    if not user.encrypted_access_token:
        raise AuthenticationError(f"No access token for user {user.id}")
    
    # Check if token is still valid (with buffer)
    buffer = timedelta(seconds=300)  # 5 minute buffer
    now = datetime.now(timezone.utc)
    
    token_expires = user.token_expires_at
    needs_refresh = True
    
    if token_expires:
        if token_expires.tzinfo is None:
            token_expires = token_expires.replace(tzinfo=timezone.utc)
        needs_refresh = (token_expires - buffer) <= now
    
    if not needs_refresh:
        # Token is still valid, just decrypt and use it
        access_token = token_service.decrypt_token(user.encrypted_access_token)
        return GmailFetcher(access_token)
    
    # Token needs refresh - do it outside SQLAlchemy context
    logger.info(f"Access token needs refresh for user {user.id}")
    
    if not user.encrypted_refresh_token:
        raise AuthenticationError(f"No refresh token for user {user.id}")
    
    refresh_token = token_service.decrypt_token(user.encrypted_refresh_token)
    
    # Refresh token using aiohttp (outside of any DB operation)
    new_tokens = await token_service.refresh_google_token(refresh_token)
    
    if not new_tokens:
        raise AuthenticationError(f"Token refresh failed for user {user.id}")
    
    new_access_token, new_refresh_token, expires_in = new_tokens
    
    # Store new tokens in database
    user.encrypted_access_token = token_service.encrypt_token(new_access_token)
    if new_refresh_token:
        user.encrypted_refresh_token = token_service.encrypt_token(new_refresh_token)
    user.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    
    db.add(user)
    await db.commit()
    
    logger.info(f"Token refreshed for user {user.id}")
    
    return GmailFetcher(new_access_token)
