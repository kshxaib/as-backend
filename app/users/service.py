from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.core.security import hash_password, verify_password, create_access_token
from app.db.models import User
from app.users.schemas import UserProfileResponse, UserRegister, UserLogin, UserCreate
from app.utils.encryption import encrypt_api_key, decrypt_api_key


def user_has_openai_key(user: User | None) -> bool:
    if not user or not user.openai_api_key_encrypted:
        return False
    try:
        decrypted = decrypt_api_key(user.openai_api_key_encrypted)
        return bool(decrypted and len(decrypted.strip()) > 10)
    except Exception:
        return False


def to_profile_response(user: User) -> UserProfileResponse:
    return UserProfileResponse(
        id=user.id,
        username=user.username or f"user_{user.id}",
        name=user.name,
        has_openai_key=user_has_openai_key(user),
        created_at=user.created_at,
    )


def register_user(db: Session, user_data: UserRegister) -> tuple[User, str]:
    existing_user = db.query(User).filter(User.username == user_data.username.strip().lower()).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken. Please choose another one.",
        )

    user = User(
        username=user_data.username.strip().lower(),
        password_hash=hash_password(user_data.password),
        name=user_data.name.strip(),
        openai_api_key_encrypted=None,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user_id=user.id, username=user.username)
    return user, token


def authenticate_user(db: Session, login_data: UserLogin) -> tuple[User, str]:
    user = db.query(User).filter(User.username == login_data.username.strip().lower()).first()
    if not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    token = create_access_token(user_id=user.id, username=user.username)
    return user, token


def update_user_openai_key(db: Session, user: User, openai_key: str) -> User:
    clean_key = openai_key.strip()
    if len(clean_key) < 20 or not clean_key.startswith("sk-"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OpenAI API key format. Keys must start with 'sk-' and be at least 20 characters.",
        )

    user.openai_api_key_encrypted = encrypt_api_key(clean_key)
    db.commit()
    db.refresh(user)
    return user


def delete_user_openai_key(db: Session, user: User) -> User:
    user.openai_api_key_encrypted = None
    db.commit()
    db.refresh(user)
    return user


def get_user_openai_key(db: Session, user_id: int) -> str:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found.",
        )

    if not user.openai_api_key_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OpenAI API key is missing. Please add your OpenAI API key in Profile settings.",
        )

    try:
        decrypted = decrypt_api_key(user.openai_api_key_encrypted)
        if not decrypted:
            raise ValueError()
        return decrypted
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to decrypt OpenAI API key. Please re-enter your key in Profile settings.",
        )


def get_user(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def get_user_all_keys(db: Session, user_id: int) -> dict[str, str]:
    """Retrieve decrypted OpenAI API key strictly from user database record."""
    user = db.query(User).filter(User.id == user_id).first()
    keys = {
        "openai": None,
    }
    if not user:
        return keys

    if user.openai_api_key_encrypted:
        try:
            keys["openai"] = decrypt_api_key(user.openai_api_key_encrypted)
        except Exception:
            pass

    return keys


def check_user_has_all_required_keys(db: Session, user_id: int) -> None:
    """Ensure user has configured their OpenAI API key."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found.")

    if not user.openai_api_key_encrypted:
        raise HTTPException(
            status_code=400,
            detail="OpenAI API Key is missing. Please add your OpenAI API key in Profile settings to enable AI features.",
        )


def create_user(db: Session, user_data: UserCreate) -> User:
    user = User(
        username=f"user_{user_data.name.lower().replace(' ', '_')}",
        password_hash=hash_password("default123"),
        name=user_data.name,
        openai_api_key_encrypted=None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user