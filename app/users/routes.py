from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.database import get_db
from app.db.models import User
from app.users.schemas import (
    OpenAIKeyUpdate,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserProfileResponse,
    UserRegister,
    UserResponse,
)
from app.users.service import (
    authenticate_user,
    create_user,
    delete_user_openai_key,
    get_user,
    register_user,
    to_profile_response,
    update_user_openai_key,
)

router = APIRouter(
    prefix="/api",
    tags=["Auth & Users"],
)


@router.post("/auth/register", response_model=TokenResponse)
def register_endpoint(user_data: UserRegister, db: Session = Depends(get_db)):
    user, token = register_user(db=db, user_data=user_data)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": to_profile_response(user),
    }


@router.post("/auth/login", response_model=TokenResponse)
def login_endpoint(login_data: UserLogin, db: Session = Depends(get_db)):
    user, token = authenticate_user(db=db, login_data=login_data)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": to_profile_response(user),
    }


@router.get("/auth/me", response_model=UserProfileResponse)
def get_current_user_profile(
    current_user: User = Depends(get_current_user),
):
    return to_profile_response(current_user)


@router.put("/auth/profile/openai-key", response_model=UserProfileResponse)
def update_openai_key_endpoint(
    payload: OpenAIKeyUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = update_user_openai_key(db=db, user=current_user, openai_key=payload.openai_api_key)
    return to_profile_response(user)


@router.delete("/auth/profile/openai-key", response_model=UserProfileResponse)
def delete_openai_key_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = delete_user_openai_key(db=db, user=current_user)
    return to_profile_response(user)


# Legacy / direct user endpoints
@router.post("/users", response_model=UserResponse)
def create_user_endpoint(user_data: UserCreate, db: Session = Depends(get_db)):
    return create_user(db=db, user_data=user_data)


@router.get("/users/{user_id}", response_model=UserProfileResponse)
def get_user_endpoint(user_id: int, db: Session = Depends(get_db)):
    user = get_user(db=db, user_id=user_id)
    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )
    return to_profile_response(user)