from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import RequireAdministrator, get_current_user
from app.db.session import get_db
from app.models.reference import (
    ControlType,
    Department,
    InspectionKind,
    Person,
    ProductionObject,
    ViolationGroup,
    ViolationType,
)
from app.models.security import User
from app.schemas.common import ReferenceCreate, ReferenceResponse, ReferenceUpdate
from app.schemas.references import (
    ObjectCreate,
    ObjectResponse,
    ObjectUpdate,
    PersonCreate,
    PersonResponse,
    PersonUpdate,
    ViolationTypeCreate,
    ViolationTypeResponse,
    ViolationTypeUpdate,
)
from app.services.audit import record_audit

router = APIRouter(prefix="/references", tags=["Справочники"])

SimpleModel = ControlType | InspectionKind | Department | ViolationGroup
SIMPLE_MODELS: dict[str, type[SimpleModel]] = {
    "control-types": ControlType,
    "inspection-kinds": InspectionKind,
    "departments": Department,
    "violation-groups": ViolationGroup,
}


def normalize_code(value: str) -> str:
    return value.strip().upper()


def get_simple_model(resource: str) -> type[SimpleModel]:
    model = SIMPLE_MODELS.get(resource)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Справочник не найден")
    return model


def reference_snapshot(item: Any) -> dict[str, Any]:
    fields = ("code", "name", "is_active", "display_order", "parent_id", "has_deadline_control")
    snapshot: dict[str, Any] = {}
    for field in fields:
        if not hasattr(item, field):
            continue
        value = getattr(item, field)
        snapshot[field] = str(value) if isinstance(value, UUID) else value
    return snapshot


def write_error(error: IntegrityError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Запись с такими данными уже существует")


@router.get("/{resource}", response_model=list[ReferenceResponse])
def list_simple_references(
    resource: str,
    include_inactive: bool = Query(default=False),
    _: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> list[SimpleModel]:
    model = get_simple_model(resource)
    statement = select(model).order_by(model.display_order, model.code)
    if not include_inactive:
        statement = statement.where(model.is_active.is_(True))
    return list(database.scalars(statement))


@router.post("/{resource}", response_model=ReferenceResponse, status_code=status.HTTP_201_CREATED)
def create_simple_reference(
    resource: str,
    payload: ReferenceCreate,
    administrator: User = RequireAdministrator,
    database: Session = Depends(get_db),
) -> SimpleModel:
    model = get_simple_model(resource)
    item = model(code=normalize_code(payload.code), name=payload.name.strip(), display_order=payload.display_order)
    database.add(item)
    database.flush()
    record_audit(database, actor_id=administrator.id, entity_type=model.__tablename__, entity_id=item.id, action="create", new_value=reference_snapshot(item))
    try:
        database.commit()
    except IntegrityError as error:
        database.rollback()
        raise write_error(error) from error
    database.refresh(item)
    return item


@router.patch("/{resource}/{item_id}", response_model=ReferenceResponse)
def update_simple_reference(
    resource: str,
    item_id: UUID,
    payload: ReferenceUpdate,
    administrator: User = RequireAdministrator,
    database: Session = Depends(get_db),
) -> SimpleModel:
    model = get_simple_model(resource)
    item = database.get(model, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Запись не найдена")
    old_value = reference_snapshot(item)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value.strip() if field == "name" and value is not None else value)
    record_audit(database, actor_id=administrator.id, entity_type=model.__tablename__, entity_id=item.id, action="update", old_value=old_value, new_value=reference_snapshot(item))
    database.commit()
    database.refresh(item)
    return item


@router.get("/objects/items", response_model=list[ObjectResponse])
def list_objects(
    include_inactive: bool = False,
    _: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> list[ProductionObject]:
    statement = select(ProductionObject).order_by(ProductionObject.display_order, ProductionObject.code)
    if not include_inactive:
        statement = statement.where(ProductionObject.is_active.is_(True))
    return list(database.scalars(statement))


@router.post("/objects/items", response_model=ObjectResponse, status_code=status.HTTP_201_CREATED)
def create_object(payload: ObjectCreate, administrator: User = RequireAdministrator, database: Session = Depends(get_db)) -> ProductionObject:
    item = ProductionObject(code=normalize_code(payload.code), name=payload.name.strip(), owner_department_id=payload.owner_department_id, display_order=payload.display_order)
    database.add(item)
    database.flush()
    record_audit(database, actor_id=administrator.id, entity_type="objects", entity_id=item.id, action="create", new_value=reference_snapshot(item))
    try:
        database.commit()
    except IntegrityError as error:
        database.rollback()
        raise write_error(error) from error
    database.refresh(item)
    return item


@router.patch("/objects/items/{item_id}", response_model=ObjectResponse)
def update_object(item_id: UUID, payload: ObjectUpdate, administrator: User = RequireAdministrator, database: Session = Depends(get_db)) -> ProductionObject:
    item = database.get(ProductionObject, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Объект не найден")
    old_value = reference_snapshot(item)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value.strip() if field == "name" and value is not None else value)
    record_audit(database, actor_id=administrator.id, entity_type="objects", entity_id=item.id, action="update", old_value=old_value, new_value=reference_snapshot(item))
    database.commit()
    database.refresh(item)
    return item


@router.get("/persons/items", response_model=list[PersonResponse])
def list_persons(include_inactive: bool = False, _: User = Depends(get_current_user), database: Session = Depends(get_db)) -> list[Person]:
    statement = select(Person).order_by(Person.display_order, Person.full_name)
    if not include_inactive:
        statement = statement.where(Person.is_active.is_(True))
    return list(database.scalars(statement))


@router.post("/persons/items", response_model=PersonResponse, status_code=status.HTTP_201_CREATED)
def create_person(payload: PersonCreate, administrator: User = RequireAdministrator, database: Session = Depends(get_db)) -> Person:
    item = Person(full_name=payload.full_name.strip(), position=payload.position, department_id=payload.department_id, display_order=payload.display_order)
    database.add(item)
    database.flush()
    record_audit(database, actor_id=administrator.id, entity_type="persons", entity_id=item.id, action="create", new_value={"full_name": item.full_name, "position": item.position})
    database.commit()
    database.refresh(item)
    return item


@router.patch("/persons/items/{item_id}", response_model=PersonResponse)
def update_person(item_id: UUID, payload: PersonUpdate, administrator: User = RequireAdministrator, database: Session = Depends(get_db)) -> Person:
    item = database.get(Person, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    old_value = {"full_name": item.full_name, "position": item.position, "department_id": str(item.department_id) if item.department_id else None, "is_active": item.is_active}
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value.strip() if field in {"full_name", "position"} and value is not None else value)
    record_audit(database, actor_id=administrator.id, entity_type="persons", entity_id=item.id, action="update", old_value=old_value, new_value={"full_name": item.full_name, "position": item.position, "is_active": item.is_active})
    database.commit()
    database.refresh(item)
    return item


@router.get("/violation-types/items", response_model=list[ViolationTypeResponse])
def list_violation_types(include_inactive: bool = False, _: User = Depends(get_current_user), database: Session = Depends(get_db)) -> list[ViolationType]:
    statement = select(ViolationType).order_by(ViolationType.code)
    if not include_inactive:
        statement = statement.where(ViolationType.is_active.is_(True))
    return list(database.scalars(statement))


@router.post("/violation-types/items", response_model=ViolationTypeResponse, status_code=status.HTTP_201_CREATED)
def create_violation_type(payload: ViolationTypeCreate, administrator: User = RequireAdministrator, database: Session = Depends(get_db)) -> ViolationType:
    item = ViolationType(**payload.model_dump(exclude={"code", "name"}), code=payload.code.strip(), name=payload.name.strip())
    database.add(item)
    database.flush()
    record_audit(database, actor_id=administrator.id, entity_type="violation_types", entity_id=item.id, action="create", new_value={"code": item.code, "name": item.name, "severity": item.severity})
    try:
        database.commit()
    except IntegrityError as error:
        database.rollback()
        raise write_error(error) from error
    database.refresh(item)
    return item


@router.patch("/violation-types/items/{item_id}", response_model=ViolationTypeResponse)
def update_violation_type(item_id: UUID, payload: ViolationTypeUpdate, administrator: User = RequireAdministrator, database: Session = Depends(get_db)) -> ViolationType:
    item = database.get(ViolationType, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Тип несоответствия не найден")
    old_value = {"group_id": str(item.group_id), "name": item.name, "severity": item.severity, "is_active": item.is_active}
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value.strip() if field == "name" and value is not None else value)
    record_audit(database, actor_id=administrator.id, entity_type="violation_types", entity_id=item.id, action="update", old_value=old_value, new_value={"group_id": str(item.group_id), "name": item.name, "severity": item.severity, "is_active": item.is_active})
    database.commit()
    database.refresh(item)
    return item
