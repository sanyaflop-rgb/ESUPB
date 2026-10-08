import importlib.util
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.assessment import AssessmentCriterion, AssessmentFact, AssessmentResult
from app.models.inspection import Inspection, RepeatDecision, RepeatLink, Violation, ViolationMeasure
from app.models.reference import ControlType, Department, Person, ProductionObject, ViolationGroup, ViolationType
from app.models.security import Role, User, UserRole
from app.services.assessment import add_working_days, compute_assessment, nth_working_day, period_bounds, save_fact

QUARTER = "quarter"
HALF_YEAR = "half_year"
NINE_MONTHS = "nine_months"
YEAR = "year"


def _migration_criteria() -> list[dict]:
    path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "20261008_01_оценка_эффективности.py"
    spec = importlib.util.spec_from_file_location("assessment_migration_seed", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return list(module.CRITERIA)


def _database() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed(database: Session, *, with_journal: bool = True) -> dict[str, object]:
    criteria = {
        item["criterion_code"]: AssessmentCriterion(
            criterion_code=item["criterion_code"],
            section_code=item["section_code"],
            section_title=item["section_title"],
            name=item["name"],
            subject_type=item["subject_type"],
            period_type=item["period_type"],
            input_type=item["input_type"],
            formula_type=item["formula_type"],
            thresholds=item["thresholds"],
            score_mapping=item["score_mapping"],
            applicability_rule=item["applicability_rule"],
            input_fields=item["input_fields"],
            is_active=True,
            display_order=item["display_order"],
            version=1,
            active_from=date(2026, 1, 1),
        )
        for item in _migration_criteria()
    }
    database.add_all(criteria.values())
    database.flush()

    pc3 = ControlType(code="PC_III", name="ПК III", display_order=1, has_deadline_control=True)
    pc2 = ControlType(code="PC_II", name="ПК II", display_order=2, has_deadline_control=False)
    rtn = ControlType(code="ROSTECHNADZOR", name="Ростехнадзор", display_order=3, has_deadline_control=True)
    gzn = ControlType(code="GAZNADZOR", name="Газнадзор", display_order=4, has_deadline_control=True)
    department_a = Department(code="A", name="Цех А")
    department_b = Department(code="B", name="Цех Б")
    object_a = ProductionObject(code="O1", name="Сосуд V-101")
    object_b = ProductionObject(code="O2", name="Сосуд V-202")
    person = Person(full_name="Иванов И. И.")
    role = Role(code="Administrator", name="Администратор")
    database.add_all([pc3, pc2, rtn, gzn, department_a, department_b, object_a, object_b, person, role])
    database.flush()
    object_a.owner_department_id = department_a.id
    object_b.owner_department_id = department_b.id
    person.department_id = department_a.id
    group = ViolationGroup(code="1", name="Организация контроля")
    database.add(group)
    database.flush()
    type_11 = ViolationType(group_id=group.id, code="1.1", name="Графики", severity=9)
    type_52 = ViolationType(group_id=group.id, code="5.2", name="Поверка", severity=4)
    type_510 = ViolationType(group_id=group.id, code="5.10", name="РПО", severity=9)
    user = User(login="admin", display_name="Администратор", password_hash="x")
    spectator = User(login="spectator", display_name="Наблюдатель", password_hash="x")
    database.add_all([type_11, type_52, type_510, user, spectator])
    database.flush()
    database.add(UserRole(user_id=user.id, role_id=role.id))
    database.flush()

    seed: dict[str, object] = {
        "criteria": criteria,
        "department_a": department_a,
        "department_b": department_b,
        "user": user,
        "spectator": spectator,
    }
    if not with_journal:
        database.commit()
        return seed

    inspection_pc3 = Inspection(
        control_type_id=pc3.id,
        document_number="1/2026",
        document_number_normalized="1/2026",
        inspection_date=date(2026, 7, 10),
        created_by_id=user.id,
        updated_by_id=user.id,
    )
    inspection_rtn = Inspection(
        control_type_id=rtn.id,
        document_number="2/2026",
        document_number_normalized="2/2026",
        inspection_date=date(2026, 8, 1),
        created_by_id=user.id,
        updated_by_id=user.id,
    )
    inspection_pc2 = Inspection(
        control_type_id=pc2.id,
        document_number="3/2026",
        document_number_normalized="3/2026",
        inspection_date=date(2026, 8, 15),
        created_by_id=user.id,
        updated_by_id=user.id,
    )
    database.add_all([inspection_pc3, inspection_rtn, inspection_pc2])
    database.flush()

    v1 = Violation(inspection_id=inspection_pc3.id, formulation="Не разработан график", violated_requirement="Т1", violation_type_id=type_11.id, severity=9, created_by_id=user.id, updated_by_id=user.id)
    v2 = Violation(inspection_id=inspection_pc3.id, formulation="Просрочена поверка", violated_requirement="Т2", violation_type_id=type_52.id, severity=4, created_by_id=user.id, updated_by_id=user.id)
    v3 = Violation(inspection_id=inspection_pc3.id, formulation="Нет клейма", violated_requirement="Т3", violation_type_id=type_52.id, severity=4, created_by_id=user.id, updated_by_id=user.id)
    v4 = Violation(inspection_id=inspection_pc3.id, formulation="Отсутствует манометр", violated_requirement="Т4", violation_type_id=type_11.id, severity=9, created_by_id=user.id, updated_by_id=user.id)
    v5 = Violation(inspection_id=inspection_rtn.id, formulation="Нет записи в журнале", violated_requirement="Т5", violation_type_id=type_52.id, severity=4, created_by_id=user.id, updated_by_id=user.id)
    v6 = Violation(inspection_id=inspection_rtn.id, formulation="Не испытан предохранительный клапан", violated_requirement="Т6", violation_type_id=type_11.id, severity=9, created_by_id=user.id, updated_by_id=user.id)
    v7 = Violation(inspection_id=inspection_pc2.id, formulation="Нарушение при РПО", violated_requirement="Т7", violation_type_id=type_11.id, severity=9, created_by_id=user.id, updated_by_id=user.id)
    v8 = Violation(inspection_id=inspection_pc2.id, formulation="Нарушение наряд-допуска", violated_requirement="Т8", violation_type_id=type_510.id, severity=9, created_by_id=user.id, updated_by_id=user.id)
    v9 = Violation(inspection_id=inspection_pc3.id, formulation="Дальний срок", violated_requirement="Т9", violation_type_id=type_52.id, severity=4, created_by_id=user.id, updated_by_id=user.id)
    database.add_all([v1, v2, v3, v4, v5, v6, v7, v8, v9])
    database.flush()

    database.add_all(
        [
            ViolationMeasure(violation_id=v1.id, department_id=department_a.id, object_id=object_a.id, person_id=person.id, elimination_measure="Разработать график", due_date=date(2026, 7, 20), elimination_date=date(2026, 7, 15)),
            ViolationMeasure(violation_id=v2.id, department_id=department_a.id, object_id=object_a.id, person_id=person.id, elimination_measure="Провести поверку", due_date=date(2026, 8, 20), elimination_date=date(2026, 8, 25), eliminated_late=True, days_overdue_at_elimination=5),
            ViolationMeasure(violation_id=v3.id, department_id=department_b.id, object_id=object_b.id, person_id=person.id, elimination_measure="Нанести клеймо", due_date=date(2026, 9, 10), elimination_date=date(2026, 9, 10)),
            ViolationMeasure(violation_id=v4.id, department_id=department_b.id, object_id=object_b.id, person_id=person.id, elimination_measure="Установить манометр", due_date=date(2026, 9, 5)),
            ViolationMeasure(violation_id=v5.id, department_id=department_a.id, object_id=object_a.id, person_id=person.id, elimination_measure="Внести запись", due_date=date(2026, 9, 1), elimination_date=date(2026, 8, 30)),
            ViolationMeasure(violation_id=v6.id, department_id=department_b.id, object_id=object_b.id, person_id=person.id, elimination_measure="Испытать клапан", due_date=date(2026, 9, 15), elimination_date=date(2026, 9, 20), eliminated_late=True, days_overdue_at_elimination=5),
            ViolationMeasure(violation_id=v7.id, department_id=department_a.id, object_id=object_a.id, person_id=person.id, elimination_measure="Устранить нарушение РПО", due_date=None),
            ViolationMeasure(violation_id=v8.id, department_id=department_b.id, object_id=object_b.id, person_id=person.id, elimination_measure="Оформить наряд-допуск", due_date=None),
            ViolationMeasure(violation_id=v9.id, department_id=department_a.id, object_id=object_a.id, person_id=person.id, elimination_measure="Дальнее мероприятие", due_date=date(2027, 1, 15)),
        ]
    )
    database.flush()
    database.add(RepeatLink(source_violation_id=v1.id, candidate_violation_id=v3.id, decision=RepeatDecision.CONFIRMED, decided_by_id=user.id))
    database.commit()
    return seed


def _item(response, code: str):
    return next(item for item in response.criteria if item.criterion_code == code)


def _save_fact(
    database: Session,
    criteria: dict,
    code: str,
    department_id,
    values: dict,
    *,
    not_applicable: bool = False,
    user,
    period_type: str = QUARTER,
    period_year: int = 2026,
    period_index: int = 3,
) -> None:
    save_fact(database, criteria[code], period_type, period_year, period_index, department_id, values, not_applicable, None, user.id)
    database.commit()


def test_criteria_seed_complete() -> None:
    items = _migration_criteria()

    assert len(items) == 24
    assert {item["subject_type"] for item in items} == {"department", "service"}
    assert sum(1 for item in items if item["subject_type"] == "department") == 12
    periods: dict[str, int] = {}
    for item in items:
        periods[item["period_type"]] = periods.get(item["period_type"], 0) + 1
    assert periods == {QUARTER: 18, HALF_YEAR: 1, YEAR: 5}
    assert [item["display_order"] for item in items] == list(range(1, 25))


def test_period_bounds_and_working_days() -> None:
    assert period_bounds(QUARTER, 3, 2026) == (date(2026, 7, 1), date(2026, 9, 30))
    assert period_bounds(QUARTER, 1, 2026) == (date(2026, 1, 1), date(2026, 3, 31))
    assert period_bounds(HALF_YEAR, 2, 2026) == (date(2026, 7, 1), date(2026, 12, 31))
    assert period_bounds(NINE_MONTHS, 1, 2026) == (date(2026, 1, 1), date(2026, 9, 30))
    assert period_bounds(YEAR, 1, 2026) == (date(2026, 1, 1), date(2026, 12, 31))
    assert nth_working_day(date(2026, 10, 1), 10) == date(2026, 10, 14)
    assert add_working_days(date(2026, 10, 14), 5) == date(2026, 10, 21)


def test_service_quarter_without_data() -> None:
    database = _database()
    seed = _seed(database, with_journal=False)
    response = compute_assessment(database, QUARTER, 2026, 3)

    assert response.subject_type == "service"
    assert response.department_name is None
    assert response.period_from == date(2026, 7, 1)
    assert response.period_to == date(2026, 9, 30)
    assert response.summary.applicable_count == 0
    assert response.summary.not_applicable_count == 18
    assert response.summary.missing_input_count == 6
    assert response.summary.average_score is None
    assert response.summary.verdict is None

    criterion_1_1_1 = _item(response, "1.1.1")
    assert criterion_1_1_1.not_applicable is True
    assert "Служба ППБиБДД" in criterion_1_1_1.reason
    criterion_1_2_3 = _item(response, "1.2.3")
    assert criterion_1_2_3.missing_input is True
    criterion_2_2_1 = _item(response, "2.2.1")
    assert criterion_2_2_1.not_applicable is True
    criterion_1_1_4 = _item(response, "1.1.4")
    assert criterion_1_1_4.not_applicable is True
    criterion_1_2_1 = _item(response, "1.2.1")
    assert criterion_1_2_1.not_applicable is True
    assert "годовой" in criterion_1_2_1.reason.lower()


def test_service_quarter_with_journal() -> None:
    database = _database()
    seed = _seed(database)
    criteria: dict = seed["criteria"]
    user: User = seed["user"]

    _save_fact(database, criteria, "1.2.3", None, {"negative_fact": False}, user=user)
    _save_fact(database, criteria, "1.2.4", None, {"deviation_days": 3}, user=user)
    _save_fact(database, criteria, "2.2.5", None, {"numerator": 1}, user=user)
    _save_fact(database, criteria, "2.2.6", None, {"numerator": 0}, user=user)
    _save_fact(database, criteria, "2.2.7", None, {"total": 2, "done_on_time": 2}, user=user)

    response = compute_assessment(database, QUARTER, 2026, 3)

    assert _item(response, "1.2.3").score == 2
    assert _item(response, "1.2.4").score == 1
    assert _item(response, "1.2.4").fact == "Отклонение 3 кал. дн."
    assert _item(response, "2.2.1").score == 0
    assert _item(response, "2.2.1").fact == "1 из 2 (50%)"
    assert _item(response, "2.2.2").score == 2
    assert _item(response, "2.2.3").score == 0
    assert _item(response, "2.2.5").score == 0
    assert _item(response, "2.2.6").not_applicable is True
    assert _item(response, "2.2.7").score == 2
    assert _item(response, "2.2.8").missing_input is True
    assert _item(response, "2.2.4").not_applicable is True

    assert response.summary.applicable_count == 7
    assert response.summary.not_applicable_count == 16
    assert response.summary.missing_input_count == 1
    assert response.summary.average_score == 1.0
    assert response.summary.verdict == "satisfactory"


def test_department_quarter_with_journal() -> None:
    database = _database()
    seed = _seed(database)
    criteria: dict = seed["criteria"]
    user: User = seed["user"]
    department_a: Department = seed["department_a"]

    _save_fact(database, criteria, "1.1.1", department_a.id, {"submitted_at": "2026-10-10"}, user=user)
    _save_fact(database, criteria, "1.1.2", department_a.id, {"periodicity_kept": True}, user=user)
    _save_fact(database, criteria, "1.1.3", department_a.id, {"negative_fact": False}, user=user)
    _save_fact(database, criteria, "2.1.2", department_a.id, {"numerator": 0}, user=user)
    _save_fact(database, criteria, "2.1.5", department_a.id, {"total": 3, "done_on_time": 3}, user=user)
    _save_fact(database, criteria, "2.1.7", department_a.id, {"permits": 10}, user=user)

    response = compute_assessment(database, QUARTER, 2026, 3, department_id=department_a.id)

    assert response.subject_type == "department"
    assert response.department_name == "Цех А"
    assert _item(response, "1.1.1").score == 2
    assert _item(response, "1.1.2").score == 2
    assert _item(response, "1.1.3").score == 2
    assert _item(response, "1.1.4").not_applicable is True
    assert _item(response, "1.1.5").not_applicable is True
    assert _item(response, "2.1.1").not_applicable is True
    assert "полугод" in _item(response, "2.1.1").reason.lower()
    assert _item(response, "2.1.2").score == 2
    assert _item(response, "2.1.3").score == 0
    assert _item(response, "2.1.4").score == 0
    assert _item(response, "2.1.4").fact == "1 из 2 (50%)"
    assert _item(response, "2.1.5").score == 2
    assert _item(response, "2.1.6").score == 2
    assert _item(response, "2.1.7").score == 1
    assert _item(response, "2.1.7").fact == "1 / 10 = 0.1"
    assert _item(response, "2.2.1").not_applicable is True
    assert "подразделение" in _item(response, "2.2.1").reason

    assert response.summary.applicable_count == 9
    assert response.summary.not_applicable_count == 15
    assert response.summary.missing_input_count == 0
    assert response.summary.average_score == 1.44
    assert response.summary.verdict == "satisfactory"


def test_report_submission_thresholds() -> None:
    database = _database()
    seed = _seed(database, with_journal=False)
    criteria: dict = seed["criteria"]
    user: User = seed["user"]
    department_a: Department = seed["department_a"]
    deadline = nth_working_day(date(2026, 10, 1), 10)
    tolerance = add_working_days(deadline, 5)

    _save_fact(database, criteria, "1.1.1", department_a.id, {"submitted_at": deadline.isoformat()}, user=user)
    assert _item(compute_assessment(database, QUARTER, 2026, 3, department_id=department_a.id), "1.1.1").score == 2

    _save_fact(database, criteria, "1.1.1", department_a.id, {"submitted_at": add_working_days(deadline, 1).isoformat()}, user=user)
    assert _item(compute_assessment(database, QUARTER, 2026, 3, department_id=department_a.id), "1.1.1").score == 1

    _save_fact(database, criteria, "1.1.1", department_a.id, {"submitted_at": add_working_days(tolerance, 1).isoformat()}, user=user)
    item = _item(compute_assessment(database, QUARTER, 2026, 3, department_id=department_a.id), "1.1.1")
    assert item.score == 0
    assert "позднее 5 рабочих дней" in item.reason

    _save_fact(database, criteria, "1.1.1", department_a.id, {"submitted_at": None}, user=user)
    item = _item(compute_assessment(database, QUARTER, 2026, 3, department_id=department_a.id), "1.1.1")
    assert item.score == 0
    assert item.fact == "Сведения не представлены"


def test_plan_deadline_year_criteria() -> None:
    database = _database()
    seed = _seed(database, with_journal=False)
    criteria: dict = seed["criteria"]
    user: User = seed["user"]
    department_a: Department = seed["department_a"]

    _save_fact(database, criteria, "1.1.4", department_a.id, {"developed_at": "2025-11-20"}, user=user, period_type=YEAR, period_index=1)
    _save_fact(database, criteria, "1.1.5", department_a.id, {"developed_at": "2025-12-31"}, user=user, period_type=YEAR, period_index=1)
    _save_fact(database, criteria, "1.2.2", None, {"developed_at": "2025-12-10"}, user=user, period_type=YEAR, period_index=1)
    response = compute_assessment(database, YEAR, 2026, 1, department_id=department_a.id)

    assert _item(response, "1.1.4").score == 2
    item_1_1_5 = _item(response, "1.1.5")
    assert item_1_1_5.score == 1
    assert "Опоздание 3 кал. дн." in item_1_1_5.reason
    assert _item(response, "1.2.2").not_applicable is True
    assert _item(response, "2.1.1").missing_input is True

    _save_fact(database, criteria, "1.1.4", department_a.id, {"developed_at": "2025-12-08"}, user=user, period_type=YEAR, period_index=1)
    item = _item(compute_assessment(database, YEAR, 2026, 1, department_id=department_a.id), "1.1.4")
    assert item.score == 0

    service = compute_assessment(database, YEAR, 2026, 1)
    item_1_2_2 = _item(service, "1.2.2")
    assert item_1_2_2.score == 2
    assert item_1_2_2.fact == "Разработан 10.12.2025 (срок — 15.12.2025)"


def test_rpo_ratio_variants() -> None:
    database = _database()
    seed = _seed(database)
    criteria: dict = seed["criteria"]
    user: User = seed["user"]
    department_a: Department = seed["department_a"]

    _save_fact(database, criteria, "2.1.7", department_a.id, {"permits": 0}, user=user)
    item = _item(compute_assessment(database, QUARTER, 2026, 3, department_id=department_a.id), "2.1.7")
    assert item.not_applicable is True
    assert "наряды-допуски" in item.reason.lower()

    _save_fact(database, criteria, "2.1.7", department_a.id, {"permits": 5}, user=user)
    assert _item(compute_assessment(database, QUARTER, 2026, 3, department_id=department_a.id), "2.1.7").score == 2

    _save_fact(database, criteria, "2.1.7", department_a.id, {"permits": 20}, user=user)
    assert _item(compute_assessment(database, QUARTER, 2026, 3, department_id=department_a.id), "2.1.7").score == 0


def test_fact_subject_isolation() -> None:
    database = _database()
    seed = _seed(database)
    criteria: dict = seed["criteria"]
    user: User = seed["user"]
    department_a: Department = seed["department_a"]
    department_b: Department = seed["department_b"]

    _save_fact(database, criteria, "1.1.1", department_a.id, {"submitted_at": "2026-10-10"}, user=user)
    _save_fact(database, criteria, "1.2.3", None, {"negative_fact": False}, user=user)

    for_b = compute_assessment(database, QUARTER, 2026, 3, department_id=department_b.id)
    item_b = _item(for_b, "1.1.1")
    assert item_b.score == 0
    assert item_b.fact == "Сведения не представлены"
    assert item_b.fact_values == {}

    for_a = compute_assessment(database, QUARTER, 2026, 3, department_id=department_a.id)
    item_a = _item(for_a, "1.1.1")
    assert item_a.score == 2
    assert item_a.fact_values == {"submitted_at": "2026-10-10"}
    assert _item(for_a, "1.2.3").not_applicable is True

    for_service = compute_assessment(database, QUARTER, 2026, 3)
    assert _item(for_service, "1.2.3").score == 2
    assert _item(for_service, "1.1.1").not_applicable is True


def test_save_fact_validation_and_upsert() -> None:
    database = _database()
    seed = _seed(database, with_journal=False)
    criteria: dict = seed["criteria"]
    user: User = seed["user"]
    department_a: Department = seed["department_a"]

    try:
        save_fact(database, criteria["1.1.1"], QUARTER, 2026, 3, None, {"submitted_at": "2026-10-10"}, False, None, user.id)
        raise AssertionError("Ожидалась ошибка для критерия подразделения без подразделения")
    except ValueError:
        database.rollback()

    try:
        save_fact(database, criteria["1.2.3"], QUARTER, 2026, 3, department_a.id, {"negative_fact": False}, False, None, user.id)
        raise AssertionError("Ожидалась ошибка для критерия Службы с подразделением")
    except ValueError:
        database.rollback()

    save_fact(database, criteria["1.1.2"], QUARTER, 2026, 3, department_a.id, {"periodicity_kept": True}, False, None, user.id)
    database.commit()
    save_fact(database, criteria["1.1.2"], QUARTER, 2026, 3, department_a.id, {"periodicity_kept": False}, False, "комментарий", user.id)
    database.commit()
    facts = database.scalars(select(AssessmentFact)).all()
    assert len(facts) == 1
    assert facts[0].values == {"periodicity_kept": False}
    assert facts[0].comment == "комментарий"

    save_fact(database, criteria["1.1.2"], QUARTER, 2026, 3, department_a.id, {"periodicity_kept": True}, True, None, user.id)
    database.commit()
    response = compute_assessment(database, QUARTER, 2026, 3, department_id=department_a.id)
    item = _item(response, "1.1.2")
    assert item.not_applicable is True
    assert item.fact_not_applicable is True
    assert item.fact_values == {}


def test_half_year_and_nine_months_periods() -> None:
    database = _database()
    seed = _seed(database, with_journal=False)
    department_a: Department = seed["department_a"]

    half = compute_assessment(database, HALF_YEAR, 2026, 2, department_id=department_a.id)
    assert half.period_from == date(2026, 7, 1)
    assert half.period_to == date(2026, 12, 31)
    assert _item(half, "2.1.1").missing_input is True
    assert _item(half, "1.1.4").not_applicable is True
    assert _item(half, "1.1.1").score == 0

    nine = compute_assessment(database, NINE_MONTHS, 2026, 1)
    assert nine.period_from == date(2026, 1, 1)
    assert nine.period_to == date(2026, 9, 30)
    assert _item(nine, "2.1.1").not_applicable is True
    assert _item(nine, "1.1.4").not_applicable is True
    assert _item(nine, "1.2.3").missing_input is True


def test_assessment_api_endpoints() -> None:
    database = _database()
    seed = _seed(database)
    criteria: dict = seed["criteria"]
    user: User = seed["user"]
    spectator: User = seed["spectator"]
    department_a: Department = seed["department_a"]

    app.dependency_overrides[get_db] = lambda: database
    app.dependency_overrides[get_current_user] = lambda: user
    client = TestClient(app)
    try:
        criteria_response = client.get("/api/v1/assessment/criteria")
        assert criteria_response.status_code == 200
        assert len(criteria_response.json()) == 24

        compute_response = client.post("/api/v1/assessment/compute", json={"period_type": QUARTER, "period_year": 2026, "period_index": 3})
        assert compute_response.status_code == 200
        assert compute_response.json()["summary"]["missing_input_count"] == 6

        fact_response = client.post(
            "/api/v1/assessment/facts",
            json={
                "criterion_id": str(criteria["1.2.3"].id),
                "period_type": QUARTER,
                "period_year": 2026,
                "period_index": 3,
                "department_id": None,
                "values": {"negative_fact": False},
                "not_applicable": False,
                "comment": None,
            },
        )
        assert fact_response.status_code == 200
        assert fact_response.json()["criterion_code"] == "1.2.3"

        facts_list = client.get("/api/v1/assessment/facts", params={"period_type": QUARTER, "period_year": 2026, "period_index": 3})
        assert facts_list.status_code == 200
        assert len(facts_list.json()) == 1

        result_response = client.post("/api/v1/assessment/results", json={"period_type": QUARTER, "period_year": 2026, "period_index": 3})
        assert result_response.status_code == 200
        result = result_response.json()
        assert result["average_score"] == 1.0
        assert result["verdict"] == "satisfactory"

        second = client.post("/api/v1/assessment/results", json={"period_type": QUARTER, "period_year": 2026, "period_index": 3})
        assert second.status_code == 200
        assert second.json()["id"] == result["id"]

        list_response = client.get("/api/v1/assessment/results", params={"period_year": 2026})
        assert list_response.status_code == 200
        assert len(list_response.json()) == 1

        detail_response = client.get(f"/api/v1/assessment/results/{result['id']}")
        assert detail_response.status_code == 200
        assert len(detail_response.json()["criteria_payload"]) == 24

        department_compute = client.post(
            "/api/v1/assessment/compute",
            json={"period_type": QUARTER, "period_year": 2026, "period_index": 3, "department_id": str(department_a.id)},
        )
        assert department_compute.status_code == 200
        assert department_compute.json()["department_name"] == "Цех А"

        missing = client.get("/api/v1/assessment/results/00000000-0000-0000-0000-000000000000")
        assert missing.status_code == 404

        app.dependency_overrides[get_current_user] = lambda: spectator
        forbidden = client.post(
            "/api/v1/assessment/facts",
            json={
                "criterion_id": str(criteria["1.2.3"].id),
                "period_type": QUARTER,
                "period_year": 2026,
                "period_index": 3,
                "values": {"negative_fact": True},
            },
        )
        assert forbidden.status_code == 403
    finally:
        app.dependency_overrides.clear()
        database.close()
