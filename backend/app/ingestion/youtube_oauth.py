import logging
import urllib.parse
from typing import Any, Dict, Optional
import httpx
from sqlalchemy.orm import Session

from backend.app.core.security import decrypt_token, encrypt_token
from backend.app.db.models import Channel
from backend.config.settings import settings

logger = logging.getLogger("yt_agent.oauth")

# Google OAuth Endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"

# Scopes needed for read and response capabilities
SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]


class YouTubeOAuthManager:
    """
    Manages OAuth 2.0 authentication flow for YouTube Data API v3 in Testing Mode.
    
    Testing Mode Instructions:
    1. Go to Google Cloud Console (https://console.cloud.google.com/)
    2. APIs & Services -> OAuth consent screen -> User Type: External -> Testing
    3. Add your personal Google account under "Test users" (bypasses Google verification!)
    4. APIs & Services -> Credentials -> Create OAuth client ID -> Web application
    5. Authorized redirect URI: http://localhost:8000/api/auth/youtube/callback
    6. Copy Client ID and Client Secret into .env
    """

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
    ):
        self.client_id = client_id if client_id is not None else settings.GOOGLE_CLIENT_ID
        self.client_secret = client_secret if client_secret is not None else settings.GOOGLE_CLIENT_SECRET
        self.redirect_uri = redirect_uri if redirect_uri is not None else settings.GOOGLE_REDIRECT_URI

    def is_configured(self) -> bool:
        """Check if real OAuth client credentials are configured (not empty or template placeholders)."""
        if not self.client_id or not self.client_secret:
            return False
        if "your_google_client_id" in self.client_id or "your_google_client_secret" in self.client_secret:
            return False
        return True

    def get_authorization_url(self, state: str = "yt_agent_oauth") -> str:
        """
        Generates Google OAuth 2.0 authorization URL for offline access (refresh tokens).
        """
        if not self.is_configured():
            raise ValueError(
                "GOOGLE_CLIENT_ID is not configured in environment variables or settings."
            )

        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(SCOPES),
            "access_type": "offline",
            "prompt": "consent",  # Forces consent screen to ensure refresh_token is returned
            "include_granted_scopes": "true",
            "state": state,
        }
        return f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"

    def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        """
        Exchanges the authorization code for access and refresh tokens.
        """
        if not self.is_configured():
            raise ValueError("Google OAuth credentials (client_id/client_secret) are not configured.")

        data = {
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code",
        }

        with httpx.Client(timeout=10.0) as client:
            resp = client.post(GOOGLE_TOKEN_URL, data=data)
            if resp.status_code != 200:
                logger.error(f"Failed to exchange OAuth code: {resp.text}")
                raise ValueError(f"Token exchange failed: {resp.status_code} - {resp.text}")
            return resp.json()

    def refresh_access_token(self, encrypted_refresh_token: str) -> str:
        """
        Decrypts stored refresh token and obtains a fresh access token.
        """
        plain_refresh = decrypt_token(encrypted_refresh_token)
        if not plain_refresh:
            raise ValueError("Unable to decrypt refresh token; invalid or missing ciphertext.")

        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": plain_refresh,
            "grant_type": "refresh_token",
        }

        with httpx.Client(timeout=10.0) as client:
            resp = client.post(GOOGLE_TOKEN_URL, data=data)
            if resp.status_code != 200:
                logger.error(f"Failed to refresh access token: {resp.text}")
                raise ValueError(f"Token refresh failed: {resp.status_code} - {resp.text}")
            payload = resp.json()
            return payload.get("access_token", "")

    def fetch_channel_info(self, access_token: str) -> Dict[str, Any]:
        """
        Fetches authenticated user's YouTube channel details via YouTube Data API v3.
        """
        headers = {"Authorization": f"Bearer {access_token}"}
        url = f"{YOUTUBE_API_BASE}/channels?part=snippet,contentDetails&mine=true"

        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code != 200:
                logger.error(f"Failed to fetch YouTube channel info: {resp.text}")
                raise ValueError(f"Channel fetch failed: {resp.status_code} - {resp.text}")
            
            data = resp.json()
            items = data.get("items", [])
            if not items:
                raise ValueError("No YouTube channel found for the authenticated Google account.")
            
            item = items[0]
            snippet = item.get("snippet", {})
            return {
                "channel_id": item.get("id"),
                "title": snippet.get("title", ""),
                "description": snippet.get("description", ""),
                "custom_url": snippet.get("customUrl", ""),
                "thumbnail_url": snippet.get("thumbnails", {}).get("default", {}).get("url", ""),
            }

    def register_or_update_channel(
        self,
        db: Session,
        channel_id: str,
        refresh_token: Optional[str] = None,
        tone_setting: str = "helpful_concise",
    ) -> Channel:
        """
        Persists channel info with Fernet-encrypted refresh token.
        """
        channel = db.query(Channel).filter(Channel.google_id == channel_id).first()
        encrypted_token = encrypt_token(refresh_token) if refresh_token else None

        if not channel:
            channel = Channel(
                google_id=channel_id,
                encrypted_refresh_token=encrypted_token,
                tone_setting=tone_setting,
            )
            db.add(channel)
        else:
            if encrypted_token:
                channel.encrypted_refresh_token = encrypted_token
            channel.tone_setting = tone_setting

        db.commit()
        db.refresh(channel)
        logger.info(f"Registered/updated channel {channel_id} (DB ID: {channel.id}) with encrypted token.")
        return channel

