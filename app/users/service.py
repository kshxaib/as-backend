from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.core.security import hash_password, verify_password, create_access_token
from app.db.models import User
from app.users.schemas import UserRegister, UserLogin, UserProfileResponse, UserCreate
from app.utils.encryption import encrypt_api_key, decrypt_api_key


def user_has_openai_key(user: User | None) -> bool:
    if not user or not user.openai_api_key_encrypted:
        return False
    try:
        decrypted = decrypt_api_key(user.openai_api_key_encrypted)
        return bool(decrypted and len(decrypted.strip()) > 5)
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
    if not clean_key.startswith("sk-") and len(clean_key) < 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OpenAI API key format. Keys typically start with 'sk-'.",
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
            detail="OpenAI API key is missing. Please add your OpenAI API key in your Profile settings to enable this AI feature.",
        )

    try:
        decrypted = decrypt_api_key(user.openai_api_key_encrypted)
        if not decrypted:
            raise ValueError()
        return decrypted
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to decrypt OpenAI API key. Please re-enter your key in your Profile settings.",
        )


def get_user(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


# Legacy support
def create_user(db: Session, user_data: UserCreate) -> User:
    encrypted_key = encrypt_api_key(user_data.openai_api_key) if user_data.openai_api_key else None
    user = User(
        username=f"user_{user_data.name.lower().replace(' ', '_')}",
        password_hash=hash_password("default123"),
        name=user_data.name,
        openai_api_key_encrypted=encrypted_key,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user