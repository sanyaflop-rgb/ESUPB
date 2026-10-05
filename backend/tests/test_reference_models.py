from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.reference import ViolationType
from app.models.security import Role


def test_reference_schema_creates_portably() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as database:
        database.add(Role(code="Administrator", name="Администратор"))
        database.commit()
        assert database.scalar(select(Role.code)) == "Administrator"


def test_violation_type_severity_is_constrained() -> None:
    constraints = ViolationType.__table__.constraints
    assert any("severity" in str(constraint.sqltext) for constraint in constraints if hasattr(constraint, "sqltext"))
