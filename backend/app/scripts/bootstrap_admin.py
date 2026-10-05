"""Create the first administrator from explicit environment settings.

Run after `alembic upgrade head` only once:
    python -m app.scripts.bootstrap_admin
"""
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.security import Role, User, UserRole
from app.services.audit import record_audit


def main() -> None:
    settings = get_settings()
    if not settings.initial_admin_login or not settings.initial_admin_password:
        raise SystemExit("Set PK_CONTROL_INITIAL_ADMIN_LOGIN and PK_CONTROL_INITIAL_ADMIN_PASSWORD in .env.")
    if len(settings.initial_admin_password) < 12:
        raise SystemExit("Initial administrator password must contain at least 12 characters.")

    with SessionLocal.begin() as database:
        login = settings.initial_admin_login.strip().casefold()
        if database.scalar(select(User).where(User.login == login)) is not None:
            raise SystemExit("The requested administrator login already exists.")
        administrator_role = database.scalar(select(Role).where(Role.code == "Administrator"))
        if administrator_role is None:
            raise SystemExit("Run `alembic upgrade head` before creating the administrator.")
        user = User(login=login, display_name=settings.initial_admin_name.strip(), password_hash=hash_password(settings.initial_admin_password))
        database.add(user)
        database.flush()
        database.add(UserRole(user_id=user.id, role_id=administrator_role.id))
        record_audit(database, actor_id=user.id, entity_type="users", entity_id=user.id, action="bootstrap_create", new_value={"login": user.login, "roles": ["Administrator"]})
    print(f"Administrator '{settings.initial_admin_login}' created.")


if __name__ == "__main__":
    main()
