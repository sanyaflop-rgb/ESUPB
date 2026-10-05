from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import RequireAdministrator, get_current_user, role_codes
from app.core.security import hash_password
from app.db.session import get_db
from app.models.security import Role, User, UserRole
from app.schemas.users import RoleResponse, UserCreate, UserResponse, UserUpdate
from app.services.audit import record_audit

router = APIRouter(prefix="/users", tags=["Пользователи и роли"])


def serialize_user(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        login=user.login,
        display_name=user.display_name,
        is_active=user.is_active,
        roles=sorted(role_codes(user)),
    )


def find_roles(database: Session, codes: list[str]) -> list[Role]:
    roles = list(database.scalars(select(Role).where(Role.code.in_(set(codes)))) )
    if len(roles) != len(set(codes)):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Указана неизвестная роль")
    return roles


@router.get("", response_model=list[UserResponse])
def list_users(
    _: User = RequireAdministrator,
    database: Session = Depends(get_db),
) -> list[UserResponse]:
    users = database.scalars(select(User).options(selectinload(User.role_links).selectinload(UserRole.role)).order_by(User.login)).all()
    return [serialize_user(user) for user in users]


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    administrator: User = RequireAdministrator,
    database: Session = Depends(get_db),
) -> UserResponse:
    user = User(
        login=payload.login.strip().casefold(),
        display_name=payload.display_name.strip(),
        password_hash=hash_password(payload.password),
    )
    database.add(user)
    database.flush()
    for role in find_roles(database, payload.role_codes):
        database.add(UserRole(user_id=user.id, role_id=role.id))
    record_audit(database, actor_id=administrator.id, entity_type="users", entity_id=user.id, action="create", new_value={"login": user.login, "roles": payload.role_codes})
    try:
        database.commit()
    except IntegrityError as error:
        database.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Логин уже используется") from error
    database.refresh(user)
    user = database.scalar(select(User).options(selectinload(User.role_links).selectinload(UserRole.role)).where(User.id == user.id))
    return serialize_user(user)


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: UUID,
    payload: UserUpdate,
    administrator: User = RequireAdministrator,
    database: Session = Depends(get_db),
) -> UserResponse:
    user = database.scalar(select(User).options(selectinload(User.role_links).selectinload(UserRole.role)).where(User.id == user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
    old_value = {"display_name": user.display_name, "is_active": user.is_active, "roles": sorted(role_codes(user))}
    if payload.display_name is not None:
        user.display_name = payload.display_name.strip()
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.role_codes is not None:
        for role_link in user.role_links:
            database.delete(role_link)
        database.flush()
        for role in find_roles(database, payload.role_codes):
            database.add(UserRole(user_id=user.id, role_id=role.id))
    database.flush()
    database.refresh(user)
    user = database.scalar(select(User).options(selectinload(User.role_links).selectinload(UserRole.role)).where(User.id == user.id))
    record_audit(database, actor_id=administrator.id, entity_type="users", entity_id=user.id, action="update", old_value=old_value, new_value={"display_name": user.display_name, "is_active": user.is_active, "roles": sorted(role_codes(user))})
    database.commit()
    return serialize_user(user)


@router.get("/roles", response_model=list[RoleResponse])
def list_roles(
    _: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> list[Role]:
    return list(database.scalars(select(Role).order_by(Role.code)))
