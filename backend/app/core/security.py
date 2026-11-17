from cryptography.fernet import Fernet
from typing import Optional
from backend.config.settings import settings

def _get_fernet() -> Fernet:
    key = settings.FERNET_SECRET_KEY
    if isinstance(key, str):
        key = key.encode("utf-8")
    return Fernet(key)

def encrypt_token(plain_token: str) -> str:
    """Encrypt sensitive OAuth refresh token before persisting to database."""
    if not plain_token:
        return ""
    fernet = _get_fernet()
    encrypted = fernet.encrypt(plain_token.encode("utf-8"))
    return encrypted.decode("utf-8")

def decrypt_token(encrypted_token: str) -> Optional[str]:
    """Decrypt stored OAuth refresh token for authorized API operations."""
    if not encrypted_token:
        return None
    fernet = _get_fernet()
    decrypted = fernet.decrypt(encrypted_token.encode("utf-8"))
    return decrypted.decode("utf-8")

