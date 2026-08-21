from sqlalchemy.orm import Session

from app.db.models import User
from app.users.schemas import UserCreate
from app.utils.encryption import encrypt_api_key
 

def create_user(db: Session, user_data: UserCreate) -> User:

    encrypted_openai_key = encrypt_api_key(user_data.openai_api_key)

    user = User(
        name=user_data.name,
        openai_api_key_encrypted=encrypted_openai_key,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def get_user(db: Session, user_id: int) -> User | None:
    """
    Find a user by primary-key ID.

    Returns:
        User object if found.
        None if the user does not exist.
    """

    return (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )