from datetime import date, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.inspection import Inspection, Violation, ViolationMeasure
from app.models.reference import ControlType, Department, Person, ProductionObject, ViolationGroup, ViolationType
from app.models.security import User
from app.services.analytics import build_analytics


def _seed(database: Session) -> dict[str, object]:
    pc3 = ControlType(code="PC_III", name="ПК III", display_order=1, has_deadline_control=True)
    pc2 = ControlType(code="PC_II", name="ПК II", display_order=2, has_deadline_control=False)
    department_a = Department(code="A", name="Цех А")
    department_b = Department(code="B", name="Цех Б")
    object_a = ProductionObject(code="O1", name="Сосуд V-101", owner_department_id=None)
    object_b = ProductionObject(code="O2", name="Сосуд V-202", owner_department_id=None)
    person = Person(full_name="Иванов И. И.", department_id=None)
    group = ViolationGroup(code="1", name="Организация контроля")
    database.add(group)
    database.flush()
    heavy_type = ViolationType(group_id=group.id, code="1.1", name="Графики", severity=9)
    light_type = ViolationType(group_id=group.id, code="5.2", name="Поверка", severity=4)
    user = User(login="admin", display_name="Администратор", password_hash="x")
    database.add_all([pc3, pc2, department_a, department_b, object_a, object_b, person, heavy_type, light_type, user])
    database.flush()
    object_a.owner_department_id = department_a.id
    object_b.owner_department_id = department_b.id
    person.department_id = department_a.id
    database.flush()

    inspection_pc3_september = Inspection(
        control_type_id=pc3.id,
        document_number="1/2026",
        document_number_normalized="1/2026",
        inspection_date=date(2026, 9, 15),
        created_by_id=user.id,
        updated_by_id=user.id,
    )
    inspection_pc3_october = Inspection(
        control_type_id=pc3.id,
        document_number="2/2026",
        document_number_normalized="2/2026",
        inspection_date=date(2026, 10, 1),
        created_by_id=user.id,
        updated_by_id=user.id,
    )
    inspection_pc2 = Inspection(
        control_type_id=pc2.id,
        document_number="3/2026",
        document_number_normalized="3/2026",
        inspection_date=date(2026, 8, 20),
        created_by_id=user.id,
        updated_by_id=user.id,
    )
    database.add_all([inspection_pc3_september, inspection_pc3_october, inspection_pc2])
    database.flush()

    eliminated_violation = Violation(
        inspection_id=inspection_pc3_september.id,
        formulation="Не разработан график",
        violated_requirement="Требование 1",
        violation_type_id=heavy_type.id,
        severity=9,
        created_by_id=user.id,
        updated_by_id=user.id,
    )
    overdue_violation = Violation(
        inspection_id=inspection_pc3_october.id,
        formulation="Отсутствует манометр",
        violated_requirement="Требование 2",
        violation_type_id=heavy_type.id,
        severity=8,
        created_by_id=user.id,
        updated_by_id=user.id,
    )
    due_soon_violation = Violation(
        inspection_id=inspection_pc3_october.id,
        formulation="Не проведена поверка",
        violated_requirement="Требование 3",
        violation_type_id=light_type.id,
        severity=4,
        created_by_id=user.id,
        updated_by_id=user.id,
    )
    pc2_violation = Violation(
        inspection_id=inspection_pc2.id,
        formulation="Замечание ПК II",
        violated_requirement="Требование 4",
        violation_type_id=light_type.id,
        severity=2,
        created_by_id=user.id,
        updated_by_id=user.id,
    )
    annulled_violation = Violation(
        inspection_id=inspection_pc3_september.id,
        formulation="Аннулировано",
        violated_requirement="Требование 5",
        violation_type_id=light_type.id,
        severity=9,
        created_by_id=user.id,
        updated_by_id=user.id,
        annulled=True,
    )
    database.add_all([eliminated_violation, overdue_violation, due_soon_violation, pc2_violation, annulled_violation])
    database.flush()

    database.add_all(
        [
            ViolationMeasure(
                violation_id=eliminated_violation.id,
                department_id=department_a.id,
                object_id=object_a.id,
                person_id=person.id,
                elimination_measure="Разработать график",
                due_date=date(2026, 9, 20),
                elimination_date=date(2026, 9, 18),
            ),
            ViolationMeasure(
                violation_id=eliminated_violation.id,
                department_id=department_b.id,
                object_id=object_b.id,
                person_id=person.id,
                elimination_measure="Заменить узел",
                due_date=date(2026, 9, 10),
                elimination_date=date(2026, 9, 12),
                eliminated_late=True,
                days_overdue_at_elimination=2,
            ),
            ViolationMeasure(
                violation_id=overdue_violation.id,
                department_id=department_b.id,
                object_id=object_b.id,
                person_id=person.id,
                elimination_measure="Установить манометр",
                due_date=date(2026, 10, 1),
            ),
            ViolationMeasure(
                violation_id=due_soon_violation.id,
                department_id=department_a.id,
                object_id=object_a.id,
                person_id=person.id,
                elimination_measure="Провести поверку",
                due_date=date.today() + timedelta(days=3),
            ),
            ViolationMeasure(
                violation_id=pc2_violation.id,
                department_id=department_a.id,
                object_id=object_a.id,
                person_id=person.id,
                elimination_measure="Исправить замечание",
                due_date=None,
            ),
        ]
    )
    database.commit()
    return {
        "department_a": department_a.id,
        "department_b": department_b.id,
        "heavy_type": heavy_type.id,
    }


def _database() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_analytics_summary_and_slices() -> None:
    database = _database()
    seed = _seed(database)
    result = build_analytics(database)

    assert result.summary.total == 3
    assert result.summary.eliminated == 1
    assert result.summary.not_eliminated == 1
    assert result.summary.overdue == 1
    assert result.summary.due_soon == 1
    assert result.summary.eliminated_late == 1
    assert result.summary.heavy == 2

    assert [item.code for item in result.by_control_type] == ["PC_III"]
    pc3 = result.by_control_type[0]
    assert (pc3.total, pc3.eliminated, pc3.overdue, pc3.heavy) == (3, 1, 1, 2)

    assert {item.severity: item.total for item in result.by_severity} == {4: 1, 8: 1, 9: 1}

    department_a = next(item for item in result.by_department if item.name == "Цех А")
    department_b = next(item for item in result.by_department if item.name == "Цех Б")
    assert (department_a.total, department_a.eliminated, department_a.not_eliminated, department_a.heavy) == (2, 1, 1, 1)
    assert (department_b.total, department_b.eliminated, department_b.overdue, department_b.heavy) == (2, 1, 1, 2)

    assert {item.name: item.total for item in result.by_object} == {"Сосуд V-101": 2, "Сосуд V-202": 2}

    assert [(point.month, point.total) for point in result.dynamics] == [("2026-09", 1), ("2026-10", 2)]
    assert result.dynamics[0].by_control_type == {"PC_III": 1}
    assert result.dynamics[1].by_control_type == {"PC_III": 2}

    assert [item.total for item in result.by_violation_type] == [2, 1]
    assert seed["heavy_type"] == result.by_violation_type[0].violation_type_id


def test_analytics_filters_narrow_the_dataset() -> None:
    database = _database()
    seed = _seed(database)

    by_department = build_analytics(database, department_id=seed["department_b"])
    assert by_department.summary.total == 2
    assert by_department.summary.overdue == 1
    assert by_department.summary.eliminated == 1
    assert by_department.summary.heavy == 2

    due_soon = build_analytics(database, status_filter="due_soon")
    assert due_soon.summary.total == 1
    assert due_soon.summary.due_soon == 1

    october = build_analytics(database, date_from=date(2026, 10, 1), date_to=date(2026, 10, 31))
    assert october.summary.total == 2
    assert [point.month for point in october.dynamics] == ["2026-10"]

    heavy = build_analytics(database, severity=9)
    assert heavy.summary.total == 1
    assert heavy.summary.eliminated_late == 1
