"""
Email Sync Service
Syncs emails from Gmail to local database
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.core.config import get_settings
from app.models.email import Email
from app.models.user import User
from app.ingestion.email_fetcher import GmailFetcher, create_gmail_fetcher_for_user
from app.ingestion.email_parser import ParsedEmail

settings = get_settings()
logger = logging.getLogger(__name__)


class EmailSyncService:
    """
    Service for syncing emails from Gmail to local database.
    Handles incremental sync using timestamps.
    """
    
    async def sync_emails_for_user(
        self,
        db: AsyncSession,
        user: User,
        max_emails: int = 100,
        since_days: int = 30
    ) -> Tuple[int, int, List[str]]:
        """
        Sync emails from Gmail for a user.
        
        Args:
            db: Database session
            user: User model with OAuth tokens
            max_emails: Maximum emails to sync
            since_days: Sync emails from last N days
            
        Returns:
            Tuple of (synced_count, skipped_count, errors)
        """
        logger.info(f"Starting email sync for user {user.id}")
        
        # Calculate sync date (ensure timezone-aware)
        if user.last_email_sync:
            # Ensure timezone-aware
            if user.last_email_sync.tzinfo is None:
                since_date = user.last_email_sync.replace(tzinfo=timezone.utc)
            else:
                since_date = user.last_email_sync
        else:
            since_date = datetime.now(timezone.utc) - timedelta(days=since_days)
        
        # Create Gmail fetcher with user's token (may refresh token)
        try:
            fetcher = await create_gmail_fetcher_for_user(db, user)
        except Exception as e:
            error_msg = f"Failed to create Gmail fetcher: {e}"
            logger.error(error_msg)
            return 0, 0, [f"Authentication failed: {str(e)}"]
        
        synced_count = 0
        skipped_count = 0
        errors = []
        
        try:
            # First, fetch all emails from Gmail (separate from DB operations)
            logger.info(f"Fetching emails from Gmail since {since_date}")
            fetched_emails = []
            async for parsed_email in fetcher.fetch_emails_since(
                since_date=since_date,
                max_results=max_emails,
                label_ids=["INBOX"]  # Only inbox for now
            ):
                fetched_emails.append(parsed_email)
            
            logger.info(f"Fetched {len(fetched_emails)} emails from Gmail")
            
            # Now process and save emails to database
            for parsed_email in fetched_emails:
                try:
                    # Check if email already exists
                    existing = await self._email_exists(
                        db, user.org_id, user.id, parsed_email.message_id
                    )
                    
                    if existing:
                        skipped_count += 1
                        continue
                    
                    # Create email record
                    email = self._create_email_from_parsed(
                        parsed_email, user.org_id, str(user.id)
                    )
                    
                    db.add(email)
                    synced_count += 1
                    
                    # Commit in batches
                    if synced_count % 20 == 0:
                        await db.commit()
                        logger.info(f"Synced {synced_count} emails so far...")
                        
                except Exception as e:
                    error_msg = f"Error syncing email {parsed_email.message_id}: {e}"
                    logger.error(error_msg)
                    print(f"\n[EMAIL FETCH ERROR] {error_msg}")
                    errors.append(f"Email {parsed_email.message_id}: {str(e)}")
            
            # Final commit
            await db.commit()
            
            # Update user's last sync time
            user.last_email_sync = datetime.now(timezone.utc)
            db.add(user)
            await db.commit()
            
            logger.info(
                f"Email sync complete for user {user.id}: "
                f"synced={synced_count}, skipped={skipped_count}, errors={len(errors)}"
            )
            
        except Exception as e:
            error_msg = f"Email sync failed: {e}"
            logger.error(error_msg)
            print(f"\n[EMAIL FETCH ERROR] {error_msg}")
            errors.append(f"Sync error: {str(e)}")
            await db.rollback()
        
        return synced_count, skipped_count, errors
    
    async def _email_exists(
        self,
        db: AsyncSession,
        org_id: str,
        user_id: str,
        message_id: str
    ) -> bool:
        """Check if email already exists in database"""
        result = await db.execute(
            select(Email.id).where(
                and_(
                    Email.org_id == org_id,
                    Email.user_id == user_id,
                    Email.message_id == message_id
                )
            ).limit(1)
        )
        return result.scalar_one_or_none() is not None
    
    def _create_email_from_parsed(
        self,
        parsed: ParsedEmail,
        org_id: str,
        user_id: str,
        provider: str = "google"
    ) -> Email:
        """Convert ParsedEmail to Email model"""
        return Email(
            org_id=org_id,
            user_id=user_id,
            message_id=parsed.message_id,
            thread_id=parsed.thread_id,
            subject=parsed.subject,
            sender=parsed.sender,
            sender_name=parsed.sender_name,
            recipients_to=",".join(parsed.recipients_to) if parsed.recipients_to else None,
            recipients_cc=",".join(parsed.recipients_cc) if parsed.recipients_cc else None,
            recipients_bcc=",".join(parsed.recipients_bcc) if parsed.recipients_bcc else None,
            sent_at=parsed.sent_at or datetime.now(timezone.utc),
            received_at=datetime.now(timezone.utc),
            body_text=parsed.body_text,
            body_html=parsed.body_html,
            has_attachments=parsed.has_attachments,
            attachment_count=parsed.attachment_count,
            labels=",".join(parsed.labels) if parsed.labels else None,
            provider=provider,
            provider_message_id=parsed.message_id
        )


# Singleton
_email_sync_service: Optional[EmailSyncService] = None


def get_email_sync_service() -> EmailSyncService:
    """Get or create EmailSyncService singleton"""
    global _email_sync_service
    if _email_sync_service is None:
        _email_sync_service = EmailSyncService()
    return _email_sync_service
