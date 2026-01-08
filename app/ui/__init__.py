"""
UI Templates Module
Provides HTML templates for email-related UI pages.
"""

from .templates import (
    get_connect_gmail_page,
    get_email_list_page,
    get_email_detail_page,
    get_oauth_error_page,
    get_oauth_success_page,
    get_oauth_missing_params_page,
    get_oauth_invalid_state_page,
)

__all__ = [
    "get_connect_gmail_page",
    "get_email_list_page", 
    "get_email_detail_page",
    "get_oauth_error_page",
    "get_oauth_success_page",
    "get_oauth_missing_params_page",
    "get_oauth_invalid_state_page",
]
