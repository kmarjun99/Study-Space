from typing import Annotated, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.core.config import settings
from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.user import TokenData

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")



async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: AsyncSession = Depends(get_db)):
    import traceback
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError as e:
        # Expired signature, bad signature, malformed token — all 401, not 500.
        # The frontend axios interceptor can redirect to /login on 401.
        credentials_exception.detail = f"Token rejected: {e}"
        raise credentials_exception
    try:
        email: str = payload.get("sub")
        if email is None:
            credentials_exception.detail = "Token payload missing sub (email)"
            raise credentials_exception
        token_data = TokenData(email=email)

        result = await db.execute(select(User).where(User.email == token_data.email))
        user = result.scalars().first()
        if user is None:
            credentials_exception.detail = f"User not found for email: {token_data.email}"
            raise credentials_exception
        return user
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Auth Dependency Error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Auth Error: {str(e)}")

async def get_current_active_user(current_user: Annotated[User, Depends(get_current_user)]):
    # If we had an 'active' field we would check it here
    return current_user


# OAuth2 scheme with auto_error=False to support optional auth
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)

async def get_current_user_optional(token: Annotated[Optional[str], Depends(oauth2_scheme_optional)], db: AsyncSession = Depends(get_db)):
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            return None
        token_data = TokenData(email=email)
    except JWTError:
        return None
    
    result = await db.execute(select(User).where(User.email == token_data.email))
    user = result.scalars().first()
    return user

async def get_current_admin(current_user: Annotated[User, Depends(get_current_user)]):
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges",
        )
    return current_user

async def get_current_super_admin(current_user: Annotated[User, Depends(get_current_user)]):
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges (Super Admin required)",
        )
    return current_user


def dev_only():
    """FastAPI dependency that 404s any request in production.

    Use to gate debug / payment-bypass endpoints that must never be
    reachable on live deployments. We return 404 (not 403) so callers
    can't even tell the route exists in production — they get the same
    response as any non-existent path. This is the standard pattern for
    hiding admin/debug surface.

    Override via env var ENABLE_DEV_BYPASS=true for explicit, auditable
    short-lived staging diagnostics. The flag is read at request time
    (not module-load time) so it can be toggled without a redeploy.
    """
    is_dev = settings.ENVIRONMENT == "development"
    explicit_override = (
        (settings.ENABLE_DEV_BYPASS or "").lower() == "true"
    )
    if not (is_dev or explicit_override):
        raise HTTPException(status_code=404, detail="Not Found")
