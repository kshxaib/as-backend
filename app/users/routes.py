from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.users.schemas import UserCreate, UserResponse
from app.users.service import create_user, get_user


router = APIRouter(
    prefix="/api/users",
    tags=["Users"],
)


@router.post("", response_model=UserResponse)
def create_user_endpoint(user_data: UserCreate, db: Session = Depends(get_db)):

    """
    Create a new AcademicStack user.

    The API keys are encrypted inside the service layer
    before being stored in PostgreSQL.
    """

    return create_user(db=db, user_data=user_data)


@router.get(
    "/{user_id}",
    response_model=UserResponse,
)
def get_user_endpoint(
    user_id: int,
    db: Session = Depends(get_db),
):
    """
    Retrieve a user by ID.

    API keys are never returned because UserResponse
    does not contain API-key fields.
    """

    user = get_user(
        db=db,
        user_id=user_id,
    )

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    return user