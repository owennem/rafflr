from datetime import datetime, timedelta
from typing import Optional
import secrets
import bcrypt
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, status, Request, Response
from fastapi.security import HTTPBearer

from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, TokenData

settings = get_settings()
security = HTTPBearer(auto_error=False)


class AuthService:
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )

    @staticmethod
    def get_password_hash(password: str) -> str:
        return bcrypt.hashpw(
            password.encode('utf-8'),
            bcrypt.gensalt()
        ).decode('utf-8')

    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
        return encoded_jwt

    @staticmethod
    def decode_token(token: str) -> Optional[TokenData]:
        try:
            payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
            user_id: int = payload.get("sub")
            if user_id is None:
                return None
            return TokenData(user_id=user_id)
        except JWTError:
            return None

    @staticmethod
    def generate_verification_token() -> str:
        return secrets.token_urlsafe(32)

    @staticmethod
    def generate_reset_token() -> str:
        return secrets.token_urlsafe(32)

    @staticmethod
    def create_user(db: Session, user_data: UserCreate) -> User:
        hashed_password = AuthService.get_password_hash(user_data.password)
        verification_token = AuthService.generate_verification_token()

        db_user = User(
            email=user_data.email,
            username=user_data.username,
            hashed_password=hashed_password,
            verification_token=verification_token,
            is_verified=False
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user

    @staticmethod
    def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            return None
        if not AuthService.verify_password(password, user.hashed_password):
            return None
        return user

    @staticmethod
    def get_user_by_email(db: Session, email: str) -> Optional[User]:
        return db.query(User).filter(User.email == email).first()

    @staticmethod
    def get_user_by_username(db: Session, username: str) -> Optional[User]:
        return db.query(User).filter(User.username == username).first()

    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
        return db.query(User).filter(User.id == user_id).first()

    @staticmethod
    def verify_user_email(db: Session, token: str) -> Optional[User]:
        user = db.query(User).filter(User.verification_token == token).first()
        if user:
            user.is_verified = True
            user.verification_token = None
            db.commit()
            db.refresh(user)
        return user

    @staticmethod
    def create_password_reset(db: Session, email: str) -> Optional[str]:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            return None
        reset_token = AuthService.generate_reset_token()
        user.reset_token = reset_token
        user.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
        db.commit()
        return reset_token

    @staticmethod
    def reset_password(db: Session, token: str, new_password: str) -> bool:
        user = db.query(User).filter(
            User.reset_token == token,
            User.reset_token_expires > datetime.utcnow()
        ).first()
        if not user:
            return False
        user.hashed_password = AuthService.get_password_hash(new_password)
        user.reset_token = None
        user.reset_token_expires = None
        db.commit()
        return True


def get_token_from_cookie(request: Request) -> Optional[str]:
    return request.cookies.get("access_token")


def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
) -> Optional[User]:
    token = get_token_from_cookie(request)
    if not token:
        return None

    token_data = AuthService.decode_token(token)
    if token_data is None or token_data.user_id is None:
        return None

    user = AuthService.get_user_by_id(db, token_data.user_id)
    return user


def get_current_user_required(
    request: Request,
    db: Session = Depends(get_db)
) -> User:
    user = get_current_user(request, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    return user


def get_current_admin(
    current_user: User = Depends(get_current_user_required)
) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


def set_auth_cookie(response: Response, token: str, request: Request):
    # Detect if running over HTTPS (production)
    is_secure = (
        request.url.scheme == "https" or
        request.headers.get("x-forwarded-proto") == "https"
    )

    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=settings.access_token_expire_minutes * 60,
        samesite="lax",
        secure=is_secure  # True in production with HTTPS
    )


def clear_auth_cookie(response: Response):
    response.delete_cookie(key="access_token")
