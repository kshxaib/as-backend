import os
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


def user_has_gemini_key(user: User | None) -> bool:
    if not user or not user.gemini_api_key_encrypted:
        return False
    try:
        decrypted = decrypt_api_key(user.gemini_api_key_encrypted)
        return bool(decrypted and len(decrypted.strip()) > 5)
    except Exception:
        return False


def user_has_groq_key(user: User | None) -> bool:
    if not user or not user.groq_api_key_encrypted:
        return False
    try:
        decrypted = decrypt_api_key(user.groq_api_key_encrypted)
        return bool(decrypted and len(decrypted.strip()) > 5)
    except Exception:
        return False


def user_has_openrouter_key(user: User | None) -> bool:
    if not user or not user.openrouter_api_key_encrypted:
        return False
    try:
        decrypted = decrypt_api_key(user.openrouter_api_key_encrypted)
        return bool(decrypted and len(decrypted.strip()) > 5)
    except Exception:
        return False


def user_has_nvidia_key(user: User | None) -> bool:
    if not user or not user.nvidia_api_key_encrypted:
        return False
    try:
        decrypted = decrypt_api_key(user.nvidia_api_key_encrypted)
        return bool(decrypted and len(decrypted.strip()) > 5)
    except Exception:
        return False


def to_profile_response(user: User) -> UserProfileResponse:
    return UserProfileResponse(
        id=user.id,
        username=user.username or f"user_{user.id}",
        name=user.name,
        has_openai_key=user_has_openai_key(user),
        has_gemini_key=user_has_gemini_key(user),
        has_groq_key=user_has_groq_key(user),
        has_openrouter_key=user_has_openrouter_key(user),
        has_nvidia_key=user_has_nvidia_key(user),
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
        gemini_api_key_encrypted=None,
        groq_api_key_encrypted=None,
        openrouter_api_key_encrypted=None,
        nvidia_api_key_encrypted=None,
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


def update_user_gemini_key(db: Session, user: User, gemini_key: str) -> User:
    clean_key = gemini_key.strip()
    if not clean_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Gemini API key format.",
        )

    user.gemini_api_key_encrypted = encrypt_api_key(clean_key)
    db.commit()
    db.refresh(user)
    return user


def update_user_groq_key(db: Session, user: User, groq_key: str) -> User:
    clean_key = groq_key.strip()
    if not clean_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Groq API key format.",
        )

    user.groq_api_key_encrypted = encrypt_api_key(clean_key)
    db.commit()
    db.refresh(user)
    return user


def update_user_openrouter_key(db: Session, user: User, openrouter_key: str) -> User:
    clean_key = openrouter_key.strip()
    if not clean_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OpenRouter API key format.",
        )

    user.openrouter_api_key_encrypted = encrypt_api_key(clean_key)
    db.commit()
    db.refresh(user)
    return user


def update_user_nvidia_key(db: Session, user: User, nvidia_key: str) -> User:
    clean_key = nvidia_key.strip()
    if not clean_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid NVIDIA API key format.",
        )

    user.nvidia_api_key_encrypted = encrypt_api_key(clean_key)
    db.commit()
    db.refresh(user)
    return user


def delete_user_openai_key(db: Session, user: User) -> User:
    user.openai_api_key_encrypted = None
    db.commit()
    db.refresh(user)
    return user


def delete_user_gemini_key(db: Session, user: User) -> User:
    user.gemini_api_key_encrypted = None
    db.commit()
    db.refresh(user)
    return user


def delete_user_groq_key(db: Session, user: User) -> User:
    user.groq_api_key_encrypted = None
    db.commit()
    db.refresh(user)
    return user


def delete_user_openrouter_key(db: Session, user: User) -> User:
    user.openrouter_api_key_encrypted = None
    db.commit()
    db.refresh(user)
    return user


def delete_user_nvidia_key(db: Session, user: User) -> User:
    user.nvidia_api_key_encrypted = None
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


def get_user_gemini_key(db: Session, user_id: int) -> str:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found.",
        )

    if not user.gemini_api_key_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gemini API key is missing. Please add your Gemini API key in your Profile settings.",
        )

    try:
        decrypted = decrypt_api_key(user.gemini_api_key_encrypted)
        if not decrypted:
            raise ValueError()
        return decrypted
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to decrypt Gemini API key. Please re-enter your key in your Profile settings.",
        )


def get_user_groq_key(db: Session, user_id: int) -> str:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found.",
        )

    if not user.groq_api_key_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Groq API key is missing. Please add your Groq API key in your Profile settings.",
        )

    try:
        decrypted = decrypt_api_key(user.groq_api_key_encrypted)
        if not decrypted:
            raise ValueError()
        return decrypted
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to decrypt Groq API key. Please re-enter your key in your Profile settings.",
        )


def get_user_openrouter_key(db: Session, user_id: int) -> str:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found.",
        )

    if not user.openrouter_api_key_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OpenRouter API key is missing. Please add your OpenRouter API key in your Profile settings.",
        )

    try:
        decrypted = decrypt_api_key(user.openrouter_api_key_encrypted)
        if not decrypted:
            raise ValueError()
        return decrypted
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to decrypt OpenRouter API key. Please re-enter your key in your Profile settings.",
        )


def get_user_nvidia_key(db: Session, user_id: int) -> str:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found.",
        )

    if not user.nvidia_api_key_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="NVIDIA API key is missing. Please add your NVIDIA API key in your Profile settings.",
        )

    try:
        decrypted = decrypt_api_key(user.nvidia_api_key_encrypted)
        if not decrypted:
            raise ValueError()
        return decrypted
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to decrypt NVIDIA API key. Please re-enter your key in your Profile settings.",
        )


def get_user(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def get_user_all_keys(db: Session, user_id: int) -> dict[str, str]:
    """
    Retrieve all decrypted API keys for a user.
    Only user-stored keys are used (no env fallback), EXCEPT OpenAI which falls back to env
    so paid users don't need to re-enter it if it's already set in .env.
    """
    user = db.query(User).filter(User.id == user_id).first()
    keys = {
        "gemini": None,
        "groq": None,
        "openrouter": None,
        "nvidia": None,
        "openai": None,
    }
    if not user:
        return keys

    if user.gemini_api_key_encrypted:
        try:
            keys["gemini"] = decrypt_api_key(user.gemini_api_key_encrypted)
        except Exception:
            pass

    if user.groq_api_key_encrypted:
        try:
            keys["groq"] = decrypt_api_key(user.groq_api_key_encrypted)
        except Exception:
            pass

    if user.openrouter_api_key_encrypted:
        try:
            keys["openrouter"] = decrypt_api_key(user.openrouter_api_key_encrypted)
        except Exception:
            pass

    if user.nvidia_api_key_encrypted:
        try:
            keys["nvidia"] = decrypt_api_key(user.nvidia_api_key_encrypted)
        except Exception:
            pass

    # OpenAI: user key first, then env fallback (optional provider)
    if user.openai_api_key_encrypted:
        try:
            keys["openai"] = decrypt_api_key(user.openai_api_key_encrypted)
        except Exception:
            pass
    if not keys["openai"]:
        keys["openai"] = os.getenv("OPENAI_API_KEY")

    return keys


def check_user_has_all_required_keys(db: Session, user_id: int) -> None:
    """Ensure user has entered all 4 required free API keys (Gemini, Groq, OpenRouter, NVIDIA NIM)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found.")

    missing = []
    if not user.gemini_api_key_encrypted:
        missing.append("Google Gemini")
    if not user.groq_api_key_encrypted:
        missing.append("Groq Cloud")
    if not user.openrouter_api_key_encrypted:
        missing.append("OpenRouter")
    if not user.nvidia_api_key_encrypted:
        missing.append("NVIDIA NIM")

    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required free API keys: {', '.join(missing)}. Please configure all 4 free keys in Profile settings to enable AI features.",
        )


# Legacy support
def create_user(db: Session, user_data: UserCreate) -> User:
    encrypted_key = encrypt_api_key(user_data.openai_api_key) if user_data.openai_api_key else None
    user = User(
        username=f"user_{user_data.name.lower().replace(' ', '_')}",
        password_hash=hash_password("default123"),
        name=user_data.name,
        openai_api_key_encrypted=encrypted_key,
        gemini_api_key_encrypted=None,
        groq_api_key_encrypted=None,
        openrouter_api_key_encrypted=None,
        nvidia_api_key_encrypted=None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user