"""
Email Parser
Parses raw MIME emails into structured data
"""
import logging
import email
from email import policy
from email.message import EmailMessage
from email.utils import parseaddr, parsedate_to_datetime
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
import re
from html import unescape
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class ParsedAttachment:
    """Parsed email attachment"""
    filename: str
    content_type: str
    size: int
    content_id: Optional[str] = None
    is_inline: bool = False


@dataclass
class ParsedEmail:
    """Parsed email structure"""
    message_id: str
    subject: Optional[str] = None
    sender: str = ""
    sender_name: Optional[str] = None
    recipients_to: List[str] = field(default_factory=list)
    recipients_cc: List[str] = field(default_factory=list)
    recipients_bcc: List[str] = field(default_factory=list)
    sent_at: Optional[datetime] = None
    body_text: Optional[str] = None
    body_html: Optional[str] = None
    thread_id: Optional[str] = None
    in_reply_to: Optional[str] = None
    references: List[str] = field(default_factory=list)
    attachments: List[ParsedAttachment] = field(default_factory=list)
    headers: Dict[str, str] = field(default_factory=dict)
    labels: List[str] = field(default_factory=list)
    
    @property
    def has_attachments(self) -> bool:
        return len(self.attachments) > 0
    
    @property
    def attachment_count(self) -> int:
        return len(self.attachments)
    
    def get_clean_text(self) -> str:
        """Get clean text content for embedding"""
        if self.body_text:
            return self._clean_text(self.body_text)
        elif self.body_html:
            return self._html_to_text(self.body_html)
        return ""
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text content"""
        if not text:
            return ""
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove email signatures (common patterns)
        signature_patterns = [
            r'--\s*\n.*',  # -- signature
            r'Sent from my (?:iPhone|iPad|Android|Samsung).*',
            r'Get Outlook for .*',
        ]
        for pattern in signature_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)
        
        return text.strip()
    
    def _html_to_text(self, html: str) -> str:
        """Convert HTML to plain text"""
        if not html:
            return ""
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove script and style elements
            for element in soup(['script', 'style', 'head', 'meta', 'link']):
                element.decompose()
            
            # Get text
            text = soup.get_text(separator=' ')
            
            # Clean up
            return self._clean_text(text)
            
        except Exception as e:
            logger.warning(f"HTML parsing failed: {e}")
            # Fallback: strip tags with regex
            text = re.sub(r'<[^>]+>', ' ', html)
            return self._clean_text(unescape(text))


class EmailParser:
    """
    Parser for raw MIME email messages.
    Handles multipart emails, attachments, and various encodings.
    """
    
    def __init__(self):
        self._policy = policy.default.clone(utf8=True)
    
    def parse_raw(self, raw_email: bytes) -> ParsedEmail:
        """
        Parse raw email bytes into structured ParsedEmail.
        
        Args:
            raw_email: Raw MIME email bytes
            
        Returns:
            ParsedEmail object with extracted data
        """
        try:
            msg = email.message_from_bytes(raw_email, policy=self._policy)
            return self._parse_message(msg)
        except Exception as e:
            logger.error(f"Failed to parse email: {e}")
            raise ValueError(f"Email parsing failed: {e}")
    
    def parse_string(self, raw_email: str) -> ParsedEmail:
        """
        Parse raw email string into structured ParsedEmail.
        
        Args:
            raw_email: Raw MIME email string
            
        Returns:
            ParsedEmail object with extracted data
        """
        try:
            msg = email.message_from_string(raw_email, policy=self._policy)
            return self._parse_message(msg)
        except Exception as e:
            logger.error(f"Failed to parse email: {e}")
            raise ValueError(f"Email parsing failed: {e}")
    
    def parse_gmail_message(self, gmail_msg: Dict[str, Any]) -> ParsedEmail:
        """
        Parse Gmail API message format.
        
        Args:
            gmail_msg: Gmail API message dict (with payload)
            
        Returns:
            ParsedEmail object with extracted data
        """
        parsed = ParsedEmail(
            message_id=gmail_msg.get("id", ""),
            thread_id=gmail_msg.get("threadId"),
            labels=gmail_msg.get("labelIds", [])
        )
        
        payload = gmail_msg.get("payload", {})
        headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}
        
        # Extract headers
        parsed.subject = headers.get("subject")
        parsed.in_reply_to = headers.get("in-reply-to")
        
        if headers.get("references"):
            parsed.references = headers["references"].split()
        
        # Parse sender
        if headers.get("from"):
            name, addr = parseaddr(headers["from"])
            parsed.sender = addr
            parsed.sender_name = name if name else None
        
        # Parse recipients
        parsed.recipients_to = self._parse_address_list(headers.get("to", ""))
        parsed.recipients_cc = self._parse_address_list(headers.get("cc", ""))
        parsed.recipients_bcc = self._parse_address_list(headers.get("bcc", ""))
        
        # Parse date
        if headers.get("date"):
            try:
                parsed.sent_at = parsedate_to_datetime(headers["date"])
            except Exception:
                parsed.sent_at = datetime.now(timezone.utc)
        
        # Extract body from parts
        self._extract_gmail_body(payload, parsed)
        
        # Store important headers
        parsed.headers = {
            "message-id": headers.get("message-id", ""),
            "from": headers.get("from", ""),
            "to": headers.get("to", ""),
            "subject": headers.get("subject", ""),
            "date": headers.get("date", "")
        }
        
        return parsed
    
    def _parse_message(self, msg: EmailMessage) -> ParsedEmail:
        """Parse email.message.EmailMessage into ParsedEmail"""
        parsed = ParsedEmail(
            message_id=msg.get("Message-ID", "") or "",
            subject=msg.get("Subject"),
            in_reply_to=msg.get("In-Reply-To"),
            thread_id=msg.get("Thread-Index") or msg.get("References", "").split()[0] if msg.get("References") else None
        )
        
        # Parse sender
        if msg.get("From"):
            name, addr = parseaddr(msg["From"])
            parsed.sender = addr
            parsed.sender_name = name if name else None
        
        # Parse recipients
        parsed.recipients_to = self._parse_address_list(msg.get("To", ""))
        parsed.recipients_cc = self._parse_address_list(msg.get("Cc", ""))
        parsed.recipients_bcc = self._parse_address_list(msg.get("Bcc", ""))
        
        # Parse references
        if msg.get("References"):
            parsed.references = msg["References"].split()
        
        # Parse date
        if msg.get("Date"):
            try:
                parsed.sent_at = parsedate_to_datetime(msg["Date"])
            except Exception:
                parsed.sent_at = datetime.now(timezone.utc)
        
        # Extract body and attachments
        self._extract_body_and_attachments(msg, parsed)
        
        # Store important headers
        parsed.headers = {
            "message-id": msg.get("Message-ID", ""),
            "from": msg.get("From", ""),
            "to": msg.get("To", ""),
            "subject": msg.get("Subject", ""),
            "date": msg.get("Date", "")
        }
        
        return parsed
    
    def _parse_address_list(self, address_string: str) -> List[str]:
        """Parse comma-separated email addresses"""
        if not address_string:
            return []
        
        addresses = []
        # Simple split - handles most cases
        for part in address_string.split(","):
            _, addr = parseaddr(part.strip())
            if addr:
                addresses.append(addr)
        
        return addresses
    
    def _extract_body_and_attachments(self, msg: EmailMessage, parsed: ParsedEmail):
        """Extract body text/html and attachments from message"""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))
                
                # Check for attachment
                if "attachment" in content_disposition:
                    self._add_attachment(part, parsed)
                elif content_type == "text/plain" and not parsed.body_text:
                    try:
                        parsed.body_text = part.get_content()
                    except Exception:
                        pass
                elif content_type == "text/html" and not parsed.body_html:
                    try:
                        parsed.body_html = part.get_content()
                    except Exception:
                        pass
                elif "inline" in content_disposition:
                    self._add_attachment(part, parsed, is_inline=True)
        else:
            content_type = msg.get_content_type()
            try:
                content = msg.get_content()
                if content_type == "text/plain":
                    parsed.body_text = content
                elif content_type == "text/html":
                    parsed.body_html = content
            except Exception:
                pass
    
    def _add_attachment(self, part: EmailMessage, parsed: ParsedEmail, is_inline: bool = False):
        """Add attachment info to parsed email"""
        filename = part.get_filename() or "unnamed"
        content_type = part.get_content_type()
        content_id = part.get("Content-ID")
        
        try:
            content = part.get_payload(decode=True)
            size = len(content) if content else 0
        except Exception:
            size = 0
        
        parsed.attachments.append(ParsedAttachment(
            filename=filename,
            content_type=content_type,
            size=size,
            content_id=content_id.strip("<>") if content_id else None,
            is_inline=is_inline
        ))
    
    def _extract_gmail_body(self, payload: Dict[str, Any], parsed: ParsedEmail):
        """Extract body from Gmail API payload structure"""
        import base64
        
        mime_type = payload.get("mimeType", "")
        
        if "parts" in payload:
            # Multipart message
            for part in payload["parts"]:
                part_mime = part.get("mimeType", "")
                
                if part_mime == "text/plain" and not parsed.body_text:
                    body_data = part.get("body", {}).get("data", "")
                    if body_data:
                        parsed.body_text = base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")
                
                elif part_mime == "text/html" and not parsed.body_html:
                    body_data = part.get("body", {}).get("data", "")
                    if body_data:
                        parsed.body_html = base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")
                
                elif part_mime.startswith("multipart/"):
                    # Nested multipart - recurse
                    self._extract_gmail_body(part, parsed)
                
                elif "filename" in part and part["filename"]:
                    # Attachment
                    parsed.attachments.append(ParsedAttachment(
                        filename=part["filename"],
                        content_type=part_mime,
                        size=part.get("body", {}).get("size", 0),
                        is_inline="inline" in str(part.get("headers", []))
                    ))
        
        elif "body" in payload and payload["body"].get("data"):
            # Single part message
            body_data = payload["body"]["data"]
            decoded = base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")
            
            if mime_type == "text/plain":
                parsed.body_text = decoded
            elif mime_type == "text/html":
                parsed.body_html = decoded


# Singleton instance
_email_parser: Optional[EmailParser] = None


def get_email_parser() -> EmailParser:
    """Get or create EmailParser singleton"""
    global _email_parser
    if _email_parser is None:
        _email_parser = EmailParser()
    return _email_parser
