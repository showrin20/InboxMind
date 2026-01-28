"""
HTML Templates for InboxMind UI
Shared templates for both authenticated and test routes.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime


# ============== Base Styles ==============

BASE_STYLES = """
<style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { 
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        min-height: 100vh;
        padding: 20px;
        color: #333;
    }
    .container { max-width: 800px; margin: 0 auto; }
    .card { 
        background: white; 
        border-radius: 16px; 
        padding: 30px; 
        box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        margin-bottom: 20px;
    }
    h1 { color: #1a73e8; margin-bottom: 10px; font-size: 28px; }
    h2 { color: #333; margin-bottom: 15px; font-size: 22px; }
    h3 { color: #555; margin-bottom: 10px; font-size: 18px; }
    p { line-height: 1.6; margin-bottom: 10px; color: #555; }
    
    .btn { 
        display: inline-block; 
        background: linear-gradient(135deg, #1a73e8 0%, #1557b0 100%);
        color: white; 
        padding: 14px 28px; 
        border-radius: 8px; 
        text-decoration: none; 
        font-weight: 600; 
        font-size: 16px;
        border: none;
        cursor: pointer;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(26, 115, 232, 0.3);
    }
    .btn:hover { 
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(26, 115, 232, 0.4);
    }
    .btn-secondary {
        background: linear-gradient(135deg, #6c757d 0%, #495057 100%);
        box-shadow: 0 4px 15px rgba(108, 117, 125, 0.3);
    }
    .btn-secondary:hover {
        box-shadow: 0 6px 20px rgba(108, 117, 125, 0.4);
    }
    .btn-success {
        background: linear-gradient(135deg, #28a745 0%, #1e7e34 100%);
        box-shadow: 0 4px 15px rgba(40, 167, 69, 0.3);
    }
    
    .warning { 
        background: linear-gradient(135deg, #fff3cd 0%, #ffeeba 100%);
        border-left: 4px solid #ffc107; 
        padding: 15px 20px; 
        border-radius: 8px; 
        margin: 20px 0; 
    }
    .success { 
        background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%);
        border-left: 4px solid #28a745; 
        padding: 15px 20px; 
        border-radius: 8px; 
        margin: 20px 0; 
    }
    .error { 
        background: linear-gradient(135deg, #f8d7da 0%, #f5c6cb 100%);
        border-left: 4px solid #dc3545; 
        padding: 15px 20px; 
        border-radius: 8px; 
        margin: 20px 0; 
    }
    .info { 
        background: linear-gradient(135deg, #e7f3ff 0%, #cce5ff 100%);
        border-left: 4px solid #1a73e8; 
        padding: 15px 20px; 
        border-radius: 8px; 
        margin: 20px 0; 
    }
    .permissions { 
        background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%);
        padding: 20px; 
        border-radius: 8px; 
        margin: 20px 0; 
    }
    
    ul, ol { padding-left: 25px; margin: 15px 0; }
    li { margin: 10px 0; line-height: 1.5; }
    
    .footer { 
        margin-top: 25px; 
        padding-top: 20px;
        border-top: 1px solid #eee;
        font-size: 13px; 
        color: #888; 
    }
    
    .header { 
        display: flex; 
        align-items: center; 
        gap: 15px; 
        margin-bottom: 20px; 
    }
    .header-icon { font-size: 40px; }
    
    .badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
    }
    .badge-test {
        background: #ffc107;
        color: #856404;
    }
    .badge-auth {
        background: #28a745;
        color: white;
    }
    
    /* Email List Styles */
    .email-list { list-style: none; padding: 0; margin: 0; }
    .email-item {
        display: flex;
        align-items: flex-start;
        padding: 15px 20px;
        border-bottom: 1px solid #eee;
        transition: background 0.2s;
        cursor: pointer;
        text-decoration: none;
        color: inherit;
    }
    .email-item:hover { background: #f8f9fa; }
    .email-item:last-child { border-bottom: none; }
    
    .email-avatar {
        width: 45px;
        height: 45px;
        border-radius: 50%;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 600;
        font-size: 18px;
        margin-right: 15px;
        flex-shrink: 0;
    }
    .email-content { flex: 1; min-width: 0; }
    .email-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px; }
    .email-sender { font-weight: 600; color: #333; font-size: 15px; }
    .email-date { font-size: 12px; color: #888; white-space: nowrap; }
    .email-subject { font-size: 14px; color: #333; margin-bottom: 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .email-preview { font-size: 13px; color: #888; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    
    .email-meta {
        display: flex;
        gap: 10px;
        align-items: center;
        margin-left: 15px;
    }
    .attachment-icon { color: #888; font-size: 14px; }
    
    /* Email Detail Styles */
    .email-detail-header {
        border-bottom: 1px solid #eee;
        padding-bottom: 20px;
        margin-bottom: 20px;
    }
    .email-detail-subject {
        font-size: 24px;
        font-weight: 600;
        color: #333;
        margin-bottom: 15px;
    }
    .email-detail-meta {
        display: flex;
        gap: 20px;
        flex-wrap: wrap;
        font-size: 14px;
        color: #666;
    }
    .email-detail-body {
        line-height: 1.8;
        color: #333;
        white-space: pre-wrap;
    }
    
    /* Pagination */
    .pagination {
        display: flex;
        justify-content: center;
        gap: 10px;
        margin-top: 20px;
        padding-top: 20px;
        border-top: 1px solid #eee;
    }
    .pagination a {
        padding: 8px 16px;
        border: 1px solid #ddd;
        border-radius: 6px;
        text-decoration: none;
        color: #1a73e8;
        transition: all 0.2s;
    }
    .pagination a:hover {
        background: #1a73e8;
        color: white;
        border-color: #1a73e8;
    }
    .pagination .disabled {
        color: #ccc;
        pointer-events: none;
    }
    
    /* Stats */
    .stats-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 15px;
        margin: 20px 0;
    }
    .stat-card {
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        padding: 20px;
        border-radius: 12px;
        text-align: center;
    }
    .stat-value {
        font-size: 32px;
        font-weight: 700;
        color: #1a73e8;
    }
    .stat-label {
        font-size: 13px;
        color: #666;
        margin-top: 5px;
    }
    
    /* Navbar */
    .navbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 15px 0;
        margin-bottom: 20px;
    }
    .navbar-brand {
        font-size: 24px;
        font-weight: 700;
        color: white;
        text-decoration: none;
    }
    .navbar-links {
        display: flex;
        gap: 20px;
    }
    .navbar-links a {
        color: rgba(255,255,255,0.9);
        text-decoration: none;
        font-weight: 500;
        transition: color 0.2s;
    }
    .navbar-links a:hover {
        color: white;
    }
    
    /* Empty State */
    .empty-state {
        text-align: center;
        padding: 60px 20px;
        color: #666;
    }
    .empty-state-icon {
        font-size: 64px;
        margin-bottom: 20px;
    }
    .empty-state h3 {
        margin-bottom: 10px;
        color: #333;
    }
</style>
"""


def _base_html(title: str, content: str, is_test: bool = False) -> str:
    """Generate base HTML page with common styles."""
    test_badge = '<span class="badge badge-test">TEST MODE</span>' if is_test else ''
    
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title} - InboxMind</title>
        {BASE_STYLES}
    </head>
    <body>
        <div class="container">
            <nav class="navbar">
                <a href="/" class="navbar-brand">📧 InboxMind {test_badge}</a>
                <div class="navbar-links">
                    <a href="/api/v1/{'test/' if is_test else ''}emails">Emails</a>
                    <a href="/api/v1/{'test/connect-gmail' if is_test else 'oauth/google'}">Connect Gmail</a>
                </div>
            </nav>
            {content}
        </div>
    </body>
    </html>
    """


# ============== Connect Gmail Page ==============

def get_connect_gmail_page(
    oauth_start_url: str = "/api/v1/oauth/google",
    is_test: bool = False,
    is_connected: bool = False
) -> str:
    """
    Generate the Gmail connection page HTML.
    
    Args:
        oauth_start_url: URL to start OAuth flow
        is_test: Whether this is for test routes
        is_connected: Whether Gmail is already connected
    """
    if is_connected:
        content = """
        <div class="card">
            <div class="header">
                <span class="header-icon">✅</span>
                <div>
                    <h1>Gmail Connected!</h1>
                    <p>Your Gmail account is already linked to InboxMind.</p>
                </div>
            </div>
            
            <div class="success">
                <strong>✓ Connection Active</strong>
                <p>Your emails are being synced and are ready for AI-powered search.</p>
            </div>
            
            <h3>What you can do now:</h3>
            <ul>
                <li><strong>View Emails</strong> - Browse your synced emails</li>
                <li><strong>Search with AI</strong> - Use natural language to find information</li>
                <li><strong>Re-sync</strong> - Fetch latest emails from Gmail</li>
            </ul>
            
            <div style="margin-top: 25px; display: flex; gap: 15px;">
                <a href="/api/v1/{prefix}emails" class="btn">📬 View Emails</a>
                <a href="/api/v1/{prefix}rag/query" class="btn btn-secondary">🔍 Search Emails</a>
            </div>
        </div>
        """
        prefix = "test/" if is_test else ""
        content = content.replace("{prefix}", prefix)
    else:
        test_warning = """
        <div class="warning">
            ⚠️ <strong>Test Mode:</strong> This is for development testing only. 
            Emails will be synced to a local database.
        </div>
        """ if is_test else ""
        
        content = f"""
        <div class="card">
            <div class="header">
                <span class="header-icon">🔗</span>
                <div>
                    <h1>Connect Your Gmail</h1>
                    <p>Link your Gmail account to enable AI-powered email search.</p>
                </div>
            </div>
            
            <div class="permissions">
                <strong>✓ Permissions we'll request:</strong>
                <ul>
                    <li><strong>Read your emails</strong> - To fetch and index email content</li>
                    <li><strong>View your email address</strong> - To identify your account</li>
                    <li><strong>View your profile info</strong> - To personalize your experience</li>
                </ul>
            </div>
            
            {test_warning}
            
            <h3>What happens next:</h3>
            <ol>
                <li>You'll be redirected to Google's consent screen</li>
                <li>Review and approve the permissions</li>
                <li>We'll automatically sync your recent emails (last 30 days)</li>
                <li>Start searching your emails with natural language!</li>
            </ol>
            
            <div style="margin-top: 25px;">
                <a href="{oauth_start_url}" class="btn">🚀 Connect Gmail Account</a>
            </div>
            
            <div class="footer">
                <p>🔒 Your data is encrypted and stored securely. We only request read-only access to your emails.</p>
                <p>By connecting, you agree to let InboxMind access your Gmail data for search and analysis.</p>
            </div>
        </div>
        """
    
    return _base_html("Connect Gmail", content, is_test)


# ============== OAuth Result Pages ==============

def get_oauth_error_page(error: str, retry_url: str = "/api/v1/oauth/google", is_test: bool = False) -> str:
    """Generate OAuth error page."""
    content = f"""
    <div class="card">
        <div class="error">
            <h2>❌ OAuth Failed</h2>
            <p><strong>Error:</strong> {error}</p>
        </div>
        <p>Something went wrong during the authorization process.</p>
        <div style="margin-top: 20px;">
            <a href="{retry_url}" class="btn">🔄 Try Again</a>
        </div>
    </div>
    """
    return _base_html("OAuth Error", content, is_test)


def get_oauth_missing_params_page(retry_url: str = "/api/v1/oauth/google", is_test: bool = False) -> str:
    """Generate missing OAuth parameters page."""
    content = f"""
    <div class="card">
        <div class="error">
            <h2>❌ Missing OAuth Parameters</h2>
            <p>The authorization response is incomplete.</p>
        </div>
        <p>This can happen if you accessed this page directly instead of through the OAuth flow.</p>
        <div style="margin-top: 20px;">
            <a href="{retry_url}" class="btn">🔄 Start Over</a>
        </div>
    </div>
    """
    return _base_html("Missing Parameters", content, is_test)


def get_oauth_invalid_state_page(retry_url: str = "/api/v1/oauth/google", is_test: bool = False) -> str:
    """Generate invalid state token page."""
    content = f"""
    <div class="card">
        <div class="error">
            <h2>❌ Invalid State Token</h2>
            <p>The security token has expired or is invalid.</p>
        </div>
        <p>This may happen if you:</p>
        <ul>
            <li>Refreshed the page during authorization</li>
            <li>Used an old or expired link</li>
            <li>Have multiple authorization tabs open</li>
        </ul>
        <div style="margin-top: 20px;">
            <a href="{retry_url}" class="btn">🔄 Try Again</a>
        </div>
    </div>
    """
    return _base_html("Invalid State", content, is_test)


def get_oauth_success_page(
    user_email: str,
    user_id: str,
    org_id: str,
    access_token: str = "",
    synced_count: int = 0,
    emails_url: str = "/api/v1/emails",
    is_test: bool = False
) -> str:
    """Generate OAuth success page with Bearer token."""
    token_section = ""
    if access_token:
        token_section = f"""
        <div class="card" style="background: #1a1a2e; color: #fff; margin-top: 20px;">
            <h3 style="color: #4ade80; margin-bottom: 15px;">🔑 Your Access Token</h3>
            <p style="color: #9ca3af; margin-bottom: 10px;">Use this Bearer token for API requests:</p>
            <div style="background: #0f0f1a; padding: 15px; border-radius: 8px; word-break: break-all; font-family: monospace; font-size: 12px; border: 1px solid #333;">
                <code id="token-code" style="color: #60a5fa;">{access_token}</code>
            </div>
            <button onclick="navigator.clipboard.writeText(document.getElementById('token-code').textContent).then(() => {{ this.textContent = '✓ Copied!'; setTimeout(() => this.textContent = '📋 Copy Token', 2000); }})" 
                    style="margin-top: 15px; background: #3b82f6; color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; font-weight: 600;">
                📋 Copy Token
            </button>
            <div style="margin-top: 15px; padding: 12px; background: #1e293b; border-radius: 6px;">
                <p style="color: #9ca3af; margin-bottom: 8px; font-size: 13px;"><strong>Usage Example:</strong></p>
                <code style="color: #fbbf24; font-size: 11px;">curl -H "Authorization: Bearer {access_token[:50]}..." http://localhost:8000/api/v1/emails</code>
            </div>
        </div>
        """
    
    content = f"""
    <div class="card">
        <div class="header">
            <span class="header-icon">🎉</span>
            <div>
                <h1>Gmail Connected Successfully!</h1>
                <p>Your account is now linked to InboxMind.</p>
            </div>
        </div>
        
        <div class="success">
            <strong>✓ Authorization Complete</strong>
            <p>Connected as: <strong>{user_email}</strong></p>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">✓</div>
                <div class="stat-label">Authenticated</div>
            </div>
        </div>
        
        <div class="info">
            <strong>Your Credentials:</strong>
            <p><strong>User ID:</strong> <code>{user_id}</code></p>
            <p><strong>Org ID:</strong> <code>{org_id}</code></p>
        </div>
        
        {token_section}
        
        <h3 style="margin-top: 25px;">What's Next?</h3>
        <ul>
            <li>Copy the Bearer token above for API requests</li>
            <li>Use the Swagger UI at <a href="/docs" style="color: #3b82f6;">/docs</a> to test endpoints</li>
            <li>Sync emails: <code>POST /api/v1/emails/sync</code></li>
            <li>Query with AI: <code>POST /api/v1/rag/query</code></li>
        </ul>
        
        <div style="margin-top: 25px; display: flex; gap: 15px; flex-wrap: wrap;">
            <a href="/docs" class="btn">📚 API Docs (Swagger)</a>
        </div>
    </div>
    """
    return _base_html("Connection Successful", content, is_test)


# ============== Email List Page ==============

def get_email_list_page(
    emails: List[Dict[str, Any]],
    total: int,
    offset: int = 0,
    limit: int = 20,
    user_id: Optional[str] = None,
    org_id: Optional[str] = None,
    base_url: str = "/api/v1/emails",
    is_test: bool = False
) -> str:
    """
    Generate the email list page HTML.
    
    Args:
        emails: List of email dictionaries
        total: Total number of emails
        offset: Current offset for pagination
        limit: Number of emails per page
        user_id: Optional user ID for test mode
        org_id: Optional org ID for test mode
        base_url: Base URL for email links
        is_test: Whether this is for test routes
    """
    if not emails:
        content = """
        <div class="card">
            <div class="empty-state">
                <div class="empty-state-icon">📭</div>
                <h3>No Emails Found</h3>
                <p>Your inbox is empty or emails haven't been synced yet.</p>
                <div style="margin-top: 20px;">
                    <a href="/api/v1/{prefix}connect-gmail" class="btn">📥 Sync Emails</a>
                </div>
            </div>
        </div>
        """
        prefix = "test/" if is_test else ""
        content = content.replace("{prefix}", prefix)
        return _base_html("Emails", content, is_test)
    
    # Build email list HTML
    email_items = ""
    for email in emails:
        sender = email.get("sender", "Unknown")
        sender_name = email.get("sender_name") or sender.split("@")[0]
        initial = sender_name[0].upper() if sender_name else "?"
        subject = email.get("subject") or "(No Subject)"
        date = email.get("sent_at", "")
        if date and "T" in date:
            date = date.split("T")[0]
        
        has_attachment = "📎" if email.get("has_attachments") else ""
        email_id = email.get("id", "")
        
        email_items += f"""
        <a href="{base_url}/{email_id}" class="email-item">
            <div class="email-avatar">{initial}</div>
            <div class="email-content">
                <div class="email-header">
                    <span class="email-sender">{sender_name}</span>
                    <span class="email-date">{date}</span>
                </div>
                <div class="email-subject">{subject}</div>
                <div class="email-preview">{sender}</div>
            </div>
            <div class="email-meta">
                <span class="attachment-icon">{has_attachment}</span>
            </div>
        </a>
        """
    
    # Pagination
    current_page = (offset // limit) + 1
    total_pages = (total + limit - 1) // limit
    
    prev_disabled = "disabled" if offset == 0 else ""
    next_disabled = "disabled" if offset + limit >= total else ""
    
    query_params = f"?limit={limit}"
    if user_id:
        query_params += f"&user_id={user_id}"
    if org_id:
        query_params += f"&org_id={org_id}"
    
    prev_url = f"{base_url}{query_params}&offset={max(0, offset - limit)}"
    next_url = f"{base_url}{query_params}&offset={offset + limit}"
    
    pagination = f"""
    <div class="pagination">
        <a href="{prev_url}" class="{prev_disabled}">← Previous</a>
        <span style="padding: 8px 16px; color: #666;">Page {current_page} of {total_pages}</span>
        <a href="{next_url}" class="{next_disabled}">Next →</a>
    </div>
    """
    
    # Stats bar
    test_info = ""
    if is_test and user_id:
        test_info = f"""
        <div class="info" style="margin-bottom: 20px;">
            <strong>Test Context:</strong> user_id={user_id}, org_id={org_id}
        </div>
        """
    
    content = f"""
    <div class="card">
        <div class="header">
            <span class="header-icon">📬</span>
            <div>
                <h1>Your Emails</h1>
                <p>Showing {len(emails)} of {total} emails</p>
            </div>
        </div>
        
        {test_info}
        
        <div class="email-list">
            {email_items}
        </div>
        
        {pagination}
    </div>
    """
    
    return _base_html("Emails", content, is_test)


# ============== Email Detail Page ==============

def get_email_detail_page(
    email: Dict[str, Any],
    back_url: str = "/api/v1/emails",
    is_test: bool = False
) -> str:
    """
    Generate the email detail page HTML.
    
    Args:
        email: Email dictionary with full details
        back_url: URL to go back to email list
        is_test: Whether this is for test routes
    """
    sender = email.get("sender", "Unknown")
    sender_name = email.get("sender_name") or sender.split("@")[0]
    subject = email.get("subject") or "(No Subject)"
    date = email.get("sent_at", "")
    
    recipients_to = email.get("recipients_to", "")
    recipients_cc = email.get("recipients_cc", "")
    
    body = email.get("body_text") or email.get("body_html") or "(No content)"
    
    # Format recipients display
    to_display = f"<p><strong>To:</strong> {recipients_to}</p>" if recipients_to else ""
    cc_display = f"<p><strong>CC:</strong> {recipients_cc}</p>" if recipients_cc else ""
    
    attachment_info = ""
    if email.get("has_attachments"):
        count = email.get("attachment_count", 1)
        attachment_info = f'<p><strong>📎 Attachments:</strong> {count} file(s)</p>'
    
    labels = ""
    if email.get("labels"):
        labels = f'<p><strong>Labels:</strong> {email.get("labels")}</p>'
    
    content = f"""
    <div class="card">
        <div style="margin-bottom: 20px;">
            <a href="{back_url}" style="color: #1a73e8; text-decoration: none;">← Back to Emails</a>
        </div>
        
        <div class="email-detail-header">
            <h1 class="email-detail-subject">{subject}</h1>
            <div class="email-detail-meta">
                <p><strong>From:</strong> {sender_name} &lt;{sender}&gt;</p>
                {to_display}
                {cc_display}
                <p><strong>Date:</strong> {date}</p>
                {attachment_info}
                {labels}
            </div>
        </div>
        
        <div class="email-detail-body">
            {body}
        </div>
    </div>
    """
    
    return _base_html(subject, content, is_test)
