from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import get_current_user, role_codes
from app.core.security import create_access_token, verify_password
from app.db.session import get_db
from app.models.security import User, UserRole
from app.schemas.auth import CurrentUserResponse, LoginRequest, TokenResponse
from app.services.audit import record_audit

router = APIRouter(prefix="/auth", tags=["Авторизация"])


@router.post("/login", response_model=TokenResponse, summary="Войти в систему")
def login(payload: LoginRequest, database: Session = Depends(get_db)) -> TokenResponse:
    login_value = payload.login.strip().casefold()
    user = database.scalar(
        select(User).options(selectinload(User.role_links).selectinload(UserRole.role)).where(User.login == login_value)
    )
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный логин или пароль")

    user.last_login_at = datetime.now(UTC)
    record_audit(
        database,
        actor_id=user.id,
        entity_type="users",
        entity_id=user.id,
        action="login",
    )
    database.commit()
    return TokenResponse(access_token=create_access_token(user.id))


@router.get("/me", response_model=CurrentUserResponse, summary="Текущий пользователь")
def read_current_user(current_user: User = Depends(get_current_user)) -> CurrentUserResponse:
    return CurrentUserResponse(
        id=current_user.id,
        login=current_user.login,
        display_name=current_user.display_name,
        roles=sorted(role_codes(current_user)),
    )
