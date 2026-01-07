"""
Ingestion Module
Email fetching and parsing utilities
"""
from app.ingestion.email_parser import EmailParser, ParsedEmail, get_email_parser
from app.ingestion.email_fetcher import (
    GmailFetcher,
    FetchResult,
    AuthenticationError,
    GmailAPIError,
    create_gmail_fetcher_for_user
)

__all__ = [
    "EmailParser",
    "ParsedEmail",
    "get_email_parser",
    "GmailFetcher",
    "FetchResult",
    "AuthenticationError",
    "GmailAPIError",
    "create_gmail_fetcher_for_user",
]
