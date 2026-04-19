"""
Authentication Module - Portfolio Manager

Simple JWT-based authentication using python-jose and passlib.
Supports login/password authentication.
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
import logging

from helper_database import (
    get_user_by_username,
    get_user_by_id,
    create_user,
    update_user
)
from config_handler import load_config, get_auth_config

logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


# =============================================================================
# Pydantic Models
# =============================================================================

class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int


class TokenData(BaseModel):
    username: Optional[str] = None
    user_id: Optional[int] = None


class User(BaseModel):
    id: int
    username: str
    is_active: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserInDB(User):
    hashed_password: str


class UserCreate(BaseModel):
    username: str
    password: str


# =============================================================================
# Password Hashing
# =============================================================================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate password hash"""
    return pwd_context.hash(password)


# =============================================================================
# JWT Token Operations
# =============================================================================

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    config = load_config()
    auth_config = get_auth_config(config)

    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire_minutes = auth_config['token_expire_minutes']
        expire = datetime.utcnow() + timedelta(minutes=expire_minutes)

    to_encode.update({"exp": expire})

    secret_key = auth_config['secret_key']
    algorithm = auth_config['algorithm']

    try:
        encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=algorithm)
        logger.debug(f"Created access token for user: {data.get('sub', 'unknown')}")
        return encoded_jwt
    except Exception as e:
        logger.error(f"Error creating JWT token: {e}")
        raise


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate JWT token"""
    config = load_config()
    auth_config = get_auth_config(config)

    try:
        payload = jwt.decode(
            token,
            auth_config['secret_key'],
            algorithms=[auth_config['algorithm']]
        )
        return payload
    except JWTError as e:
        logger.warning(f"Invalid token: {e}")
        return None


# =============================================================================
# User Authentication
# =============================================================================

def authenticate_user(username: str, password: str) -> Optional[UserInDB]:
    """Authenticate user with username and password"""
    user_data = get_user_by_username(username)

    if not user_data:
        logger.warning(f"Authentication failed: User '{username}' not found")
        return None

    if not user_data.get('is_active', True):
        logger.warning(f"Authentication failed: User '{username}' is inactive")
        return None

    hashed_password = user_data.get('hashed_password', '')

    if not verify_password(password, hashed_password):
        logger.warning(f"Authentication failed: Invalid password for '{username}'")
        return None

    logger.info(f"User '{username}' authenticated successfully")
    return UserInDB(**user_data)


def get_current_user_from_token(token: str = Depends(oauth2_scheme)) -> UserInDB:
    """Get current user from JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_token(token)
    if payload is None:
        raise credentials_exception

    username: str = payload.get("sub")
    user_id: int = payload.get("user_id")

    if username is None:
        raise credentials_exception

    user_data = get_user_by_username(username)
    if user_data is None:
        logger.error(f"Token valid but user '{username}' not found in database")
        raise credentials_exception

    return UserInDB(**user_data)


async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """Dependency to get current authenticated user"""
    user_in_db = get_current_user_from_token(token)
    return User(
        id=user_in_db.id,
        username=user_in_db.username,
        is_active=user_in_db.is_active,
        created_at=user_in_db.created_at
    )


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Dependency to get current active user"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user


# =============================================================================
# User Registration
# =============================================================================

def register_user(username: str, password: str) -> User:
    """Register new user with password"""
    # Check if user already exists
    existing = get_user_by_username(username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{username}' already exists"
        )

    hashed_password = get_password_hash(password)

    user_data = {
        'id': None,  # Will be auto-assigned
        'username': username,
        'hashed_password': hashed_password,
        'is_active': True,
        'created_at': datetime.utcnow()
    }

    try:
        created = create_user(user_data)
        logger.info(f"Registered new user: {username}")
        return User(
            id=created['id'],
            username=created['username'],
            is_active=created['is_active'],
            created_at=created['created_at']
        )
    except Exception as e:
        logger.error(f"Error registering user '{username}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating user"
        )


def change_user_password(user_id: int, new_password: str) -> bool:
    """Change user password"""
    hashed_password = get_password_hash(new_password)

    user = update_user(user_id, {'hashed_password': hashed_password})
    if user:
        logger.info(f"Password changed for user ID {user_id}")
        return True

    logger.warning(f"Failed to change password: User ID {user_id} not found")
    return False


# =============================================================================
# Login Handler
# =============================================================================

def handle_login(form_data: OAuth2PasswordRequestForm) -> Token:
    """Handle login request and return token"""
    user = authenticate_user(form_data.username, form_data.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    config = load_config()
    auth_config = get_auth_config(config)
    expires_delta = timedelta(minutes=auth_config['token_expire_minutes'])

    access_token = create_access_token(
        data={"sub": user.username, "user_id": user.id},
        expires_delta=expires_delta
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=auth_config['token_expire_minutes'] * 60
    )


# =============================================================================
# Admin / Setup Functions
# =============================================================================

def create_admin_user(username: str = "admin", password: str = "admin") -> Optional[User]:
    """Create default admin user if no users exist"""
    # Check if any users exist
    from helper_csv import _read_csv, USERS_FILE

    try:
        users = _read_csv(USERS_FILE)
        if users:
            logger.debug("Users already exist, skipping admin creation")
            return None
    except Exception:
        pass  # File doesn't exist yet

    try:
        return register_user(username, password)
    except HTTPException:
        logger.warning("Could not create default admin user")
        return None


def check_auth_enabled() -> bool:
    """Check if authentication is enabled in config"""
    try:
        config = load_config()
        return get_auth_config(config)['enabled']
    except Exception:
        return True  # Default to enabled
