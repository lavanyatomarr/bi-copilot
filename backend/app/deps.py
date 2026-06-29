from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .core.security import decode_access_token
from .db import get_db
from .models.user import User

# Tells FastAPI/Swagger where the login endpoint is, and to expect a Bearer token.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Protect any endpoint by adding this as a dependency.

    Flow: read Bearer token -> verify signature/expiry -> load the user.
    Any failure -> 401 Unauthorized.
    """
    creds_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        email = payload.get("sub")
        if email is None:
            raise creds_error
    except ValueError:
        raise creds_error

    user = db.query(User).filter(User.email == email).first()
    if user is None or not user.is_active:
        raise creds_error
    return user
