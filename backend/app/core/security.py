from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from ..config import settings

# bcrypt with the default cost factor (12). Deliberately slow = harder to brute-force.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """One-way hash a password before storing it."""
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Check a typed password against the stored hash (no decryption needed)."""
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str, role: str) -> str:
    """Build a signed JWT carrying the user's identity + an expiry."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": subject, "role": role, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Verify the signature + expiry, returning the payload. Raises on tampering/expiry."""
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise ValueError("invalid or expired token")
