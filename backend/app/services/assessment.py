"""Движок оценки эффективности производственного контроля.

Правила критериев хранятся в БД (assessment_criteria); модуль только
исполняет правила и собирает объяснение «Факт / Порог / Балл / Причина».
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assessment import (
    AssessmentCriterion,
    AssessmentFact,
    AssessmentPeriodType,
    AssessmentSubjectType,
)
from app.models.inspection import Inspection, RepeatDecision, RepeatLink, Violation, ViolationMeasure
from app.models.reference import ControlType, Department, ViolationType
from app.schemas.assessment import (
    AssessmentCriterionResult,
    AssessmentSummary,
    AssessmentComputeResponse,
)

SERVICE_NAME = "Служба промышленной, пожарной безопасности и безопасности дорожного движения"
SERVICE_SUBJECT_KEY = "service"

PERIOD_SPANS: dict[str, int] = {
    AssessmentPeriodType.QUARTER: 1,
    AssessmentPeriodType.HALF_YEAR: 2,
    AssessmentPeriodType.NINE_MONTHS: 3,
    AssessmentPeriodType.YEAR: 4,
}

PERIOD_LABELS: dict[str, str] = {
    AssessmentPeriodType.QUARTER: "Квартал",
    AssessmentPeriodType.HALF_YEAR: "Полугодие",
    AssessmentPeriodType.NINE_MONTHS: "9 месяцев",
    AssessmentPeriodType.YEAR: "Год",
}

VERDICT_SATISFACTORY = "satisfactory"
VERDICT_UNSATISFACTORY = "unsatisfactory"
VERDICT_LABELS = {VERDICT_SATISFACTORY: "Удовлетворительно", VERDICT_UNSATISFACTORY: "Неудовлетворительно"}


def period_bounds(period_type: str, period_index: int, year: int) -> tuple[date, date]:
    if period_type == AssessmentPeriodType.QUARTER:
        starts = {1: (1, 1), 2: (4, 1), 3: (7, 1), 4: (10, 1)}
        ends = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}
        start_month, start_day = starts[period_index]
        end_month, end_day = ends[period_index]
    elif period_type == AssessmentPeriodType.HALF_YEAR:
        start_month, start_day = (1, 1) if period_index == 1 else (7, 1)
        end_month, end_day = (6, 30) if period_index == 1 else (12, 31)
    elif period_type == AssessmentPeriodType.NINE_MONTHS:
        start_month, start_day, end_month, end_day = 1, 1, 9, 30
    else:
        start_month, start_day, end_month, end_day = 1, 1, 12, 31
    return date(year, start_month, start_day), date(year, end_month, end_day)


def add_working_days(start: date, days: int) -> date:
    current = start
    added = 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() < 5:
            added += 1
    return current


def nth_working_day(month_start: date, number: int) -> date:
    current = month_start
    counted = 0
    while True:
        if current.weekday() < 5:
            counted += 1
            if counted == number:
                return current
        current += timedelta(days=1)


def month_after(value: date) -> date:
    return date(value.year + 1, 1, 1) if value.month == 12 else date(value.year, value.month + 1, 1)


def subject_key_for(subject_type: str, department_id: UUID | None) -> str:
    if subject_type == AssessmentSubjectType.DEPARTMENT:
        if department_id is None:
            raise ValueError("Для критерия подразделения не указано подразделение")
        return f"department:{department_id}"
    return SERVICE_SUBJECT_KEY


def format_date(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def format_percent(numerator: int, denominator: int) -> str:
    share = numerator / denominator * 100 if denominator else 0.0
    return f"{share:.1f}".rstrip("0").rstrip(".")


@dataclass
class ScopeStats:
    total: int = 0
    heavy: int = 0
    repeat: int = 0
    measures_arrived: int = 0
    measures_on_time: int = 0

    @property
    def on_time_share_percent(self) -> float:
        return self.measures_on_time / self.measures_arrived * 100 if self.measures_arrived else 0.0


def load_scope_stats(
    database: Session,
    date_from: date,
    date_to: date,
    control_codes: list[str],
    department_id: UUID | None = None,
    violation_type_codes: list[str] | None = None,
) -> ScopeStats:
    statement = (
        select(Violation.id, Violation.severity)
        .join(Inspection, Violation.inspection_id == Inspection.id)
        .join(ControlType, Inspection.control_type_id == ControlType.id)
        .where(
            Violation.annulled.is_(False),
            ControlType.code.in_(control_codes),
            Inspection.inspection_date >= date_from,
            Inspection.inspection_date <= date_to,
        )
    )
    if violation_type_codes is not None:
        statement = statement.join(ViolationType, Violation.violation_type_id == ViolationType.id).where(
            ViolationType.code.in_(violation_type_codes)
        )
    rows = database.execute(statement).all()
    violation_ids = [row.id for row in rows]
    stats = ScopeStats(total=len(rows))
    if not rows:
        return stats

    if department_id is not None:
        scoped = database.execute(
            select(ViolationMeasure.violation_id).where(
                ViolationMeasure.violation_id.in_(violation_ids),
                ViolationMeasure.department_id == department_id,
            )
        ).scalars().unique()
        scoped_ids = set(scoped)
    else:
        scoped_ids = set(violation_ids)

    stats.total = len(scoped_ids)
    if not scoped_ids:
        return stats

    severity_by_id = {row.id: row.severity for row in rows}
    stats.heavy = sum(1 for identifier in scoped_ids if severity_by_id[identifier] >= 8)

    repeat_candidates = database.execute(
        select(RepeatLink.candidate_violation_id).where(
            RepeatLink.decision == RepeatDecision.CONFIRMED,
            RepeatLink.candidate_violation_id.in_(scoped_ids),
        )
    ).scalars().unique()
    stats.repeat = len(set(repeat_candidates))

    today = datetime.now(UTC).date()
    measure_statement = select(ViolationMeasure).where(ViolationMeasure.violation_id.in_(scoped_ids))
    if department_id is not None:
        measure_statement = measure_statement.where(ViolationMeasure.department_id == department_id)
    for measure in database.scalars(measure_statement):
        if measure.due_date is None or measure.due_date > today:
            continue
        stats.measures_arrived += 1
        on_time = measure.eliminated_during_inspection or (
            measure.elimination_date is not None and measure.elimination_date <= measure.due_date
        )
        if on_time and not measure.eliminated_late:
            stats.measures_on_time += 1
    return stats


def score_share_bad(numerator: int, denominator: int) -> int | None:
    if denominator == 0:
        return None
    if numerator * 10 < denominator:
        return 2
    if numerator * 10 <= denominator * 3:
        return 1
    return 0


def score_share_on_time(numerator: int, denominator: int) -> int | None:
    if denominator == 0:
        return None
    if numerator == denominator:
        return 2
    if numerator * 10 >= denominator * 7:
        return 1
    return 0


def score_rpo_ratio(numerator: int, denominator: int) -> int | None:
    if denominator == 0:
        return None
    if numerator * 10 < denominator:
        return 0
    if numerator * 10 == denominator:
        return 1
    return 2


@dataclass
class CriterionOutcome:
    score: int | None
    not_applicable: bool
    missing_input: bool
    fact: str | None
    threshold: str | None
    reason: str


def _fact_value(fact: AssessmentFact | None, key: str) -> object | None:
    if fact is None:
        return None
    return fact.values.get(key)


def _int_value(value: object | None) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _date_value(value: object | None) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _evaluate_report_submission(
    criterion: AssessmentCriterion, fact: AssessmentFact | None, period_to: date
) -> CriterionOutcome:
    thresholds = criterion.thresholds
    next_month = month_after(period_to)
    deadline = nth_working_day(next_month, int(thresholds["working_days_limit"]))
    tolerance = add_working_days(deadline, int(thresholds["tolerance_working_days"]))
    threshold_text = (
        f"не позднее {thresholds['working_days_limit']} раб. дней месяца, следующего за кварталом "
        f"({format_date(deadline)}); +{thresholds['tolerance_working_days']} раб. дней — балл 1"
    )
    submitted_at = _date_value(_fact_value(fact, "submitted_at"))
    if submitted_at is None:
        return CriterionOutcome(
            score=0,
            not_applicable=False,
            missing_input=False,
            fact="Сведения не представлены",
            threshold=threshold_text,
            reason="Сведения не представлены или введена пустая дата — балл 0",
        )
    if submitted_at <= deadline:
        score, reason = 2, "Сведения представлены в установленный срок"
    elif submitted_at <= tolerance:
        score, reason = 1, f"Опоздание {(submitted_at - deadline).days} кал. дн., в пределах 5 рабочих дней"
    else:
        score, reason = 0, "Сведения представлены позднее 5 рабочих дней установленного срока"
    return CriterionOutcome(
        score=score,
        not_applicable=False,
        missing_input=False,
        fact=f"Представлены {format_date(submitted_at)} (срок — {format_date(deadline)})",
        threshold=threshold_text,
        reason=reason,
    )


def _evaluate_plan_deadline(criterion: AssessmentCriterion, fact: AssessmentFact | None, period_year: int) -> CriterionOutcome:
    thresholds = criterion.thresholds
    deadline = date(period_year - 1, int(thresholds["deadline_month"]), int(thresholds["deadline_day"]))
    tolerance = add_working_days(deadline, int(thresholds["tolerance_working_days"]))
    threshold_text = (
        f"не позднее {format_date(deadline)}; позднее — балл 0; "
        f"в пределах {thresholds['tolerance_working_days']} раб. дней — балл 1"
    )
    developed_at = _date_value(_fact_value(fact, "developed_at"))
    if developed_at is None:
        return CriterionOutcome(
            score=0,
            not_applicable=False,
            missing_input=False,
            fact="Не разработан",
            threshold=threshold_text,
            reason="Документ не разработан — балл 0",
        )
    if developed_at <= deadline:
        score, reason = 2, "Разработан в установленный срок"
    elif developed_at <= tolerance:
        score, reason = 1, f"Опоздание {(developed_at - deadline).days} кал. дн., в пределах 5 рабочих дней"
    else:
        score, reason = 0, "Разработан позднее 5 рабочих дней установленного срока"
    return CriterionOutcome(
        score=score,
        not_applicable=False,
        missing_input=False,
        fact=f"Разработан {format_date(developed_at)} (срок — {format_date(deadline)})",
        threshold=threshold_text,
        reason=reason,
    )


def _evaluate_binary_choice(criterion: AssessmentCriterion, fact: AssessmentFact | None) -> CriterionOutcome:
    thresholds = criterion.thresholds
    field_key = criterion.input_fields[0]["key"] if criterion.input_fields else "negative_fact"
    value = _fact_value(fact, field_key)
    if value is None:
        return CriterionOutcome(
            score=None,
            not_applicable=False,
            missing_input=True,
            fact=None,
            threshold=f"да — балл {thresholds['true_score']}; нет — балл {thresholds['false_score']}",
            reason="Введите исходные данные (да/нет)",
        )
    chosen = bool(value)
    score = int(thresholds["true_score"]) if chosen else int(thresholds["false_score"])
    fact_text = "Да" if chosen else "Нет"
    return CriterionOutcome(
        score=score,
        not_applicable=False,
        missing_input=False,
        fact=fact_text,
        threshold=f"да — балл {thresholds['true_score']}; нет — балл {thresholds['false_score']}",
        reason=f"Выбрано «{fact_text}» — балл {score}",
    )


def _evaluate_schedule_deviation(criterion: AssessmentCriterion, fact: AssessmentFact | None) -> CriterionOutcome:
    tolerance_days = int(criterion.thresholds["tolerance_days"])
    threshold_text = f"0 дн. — балл 2; до {tolerance_days} дн. — балл 1; более {tolerance_days} дн. — балл 0"
    deviation = _int_value(_fact_value(fact, "deviation_days"))
    if deviation is None:
        return CriterionOutcome(
            score=None,
            not_applicable=False,
            missing_input=True,
            fact=None,
            threshold=threshold_text,
            reason="Введите максимальное отклонение от графика",
        )
    deviation = max(deviation, 0)
    if deviation == 0:
        score, reason = 2, "График выполнен в установленные сроки"
    elif deviation <= tolerance_days:
        score, reason = 1, f"Отклонение {deviation} кал. дн., в пределах {tolerance_days} дней"
    else:
        score, reason = 0, f"Отклонение {deviation} кал. дн. превышает {tolerance_days} дней"
    return CriterionOutcome(
        score=score,
        not_applicable=False,
        missing_input=False,
        fact=f"Отклонение {deviation} кал. дн.",
        threshold=threshold_text,
        reason=reason,
    )


def _evaluate_share_on_time_manual(criterion: AssessmentCriterion, fact: AssessmentFact | None) -> CriterionOutcome:
    on_time_from = int(criterion.thresholds["on_time_from"])
    threshold_text = f"менее {on_time_from}% — балл 0; {on_time_from}–99% — балл 1; 100% — балл 2"
    total = _int_value(_fact_value(fact, "total"))
    done = _int_value(_fact_value(fact, "done_on_time"))
    if total is None or done is None:
        return CriterionOutcome(
            score=None,
            not_applicable=False,
            missing_input=True,
            fact=None,
            threshold=threshold_text,
            reason="Введите число мероприятий и выполненных в срок",
        )
    if total == 0:
        return CriterionOutcome(
            score=None,
            not_applicable=True,
            missing_input=False,
            fact="Мероприятий нет",
            threshold=threshold_text,
            reason="За период отсутствуют соответствующие мероприятия — Н/П",
        )
    if done > total or done < 0:
        return CriterionOutcome(
            score=None,
            not_applicable=False,
            missing_input=True,
            fact=f"Выполнено в срок {done} из {total}",
            threshold=threshold_text,
            reason="Число выполненных в срок не может превышать общее число мероприятий",
        )
    score = score_share_on_time(done, total)
    share = format_percent(done, total)
    reason = f"Выполнено в срок {done} из {total} ({share}%)"
    if score == 2:
        reason += " — все мероприятия выполнены в срок"
    elif score == 1:
        reason += f" — доля в диапазоне {on_time_from}–99%"
    else:
        reason += f" — доля менее {on_time_from}%"
    return CriterionOutcome(
        score=score,
        not_applicable=False,
        missing_input=False,
        fact=f"{done} из {total} ({share}%)",
        threshold=threshold_text,
        reason=reason,
    )


def _evaluate_check_count(criterion: AssessmentCriterion, fact: AssessmentFact | None) -> CriterionOutcome:
    many_from = int(criterion.thresholds["many_from"])
    threshold_text = f"0 — балл 0; 1 — балл 1; {many_from} и более — балл 2"
    count = _int_value(_fact_value(fact, "checks_count"))
    if count is None:
        return CriterionOutcome(
            score=None,
            not_applicable=False,
            missing_input=True,
            fact=None,
            threshold=threshold_text,
            reason="Введите число целевых проверок РПО",
        )
    count = max(count, 0)
    if count == 0:
        score, reason = 0, "Целевые проверки РПО не проведены"
    elif count < many_from:
        score, reason = 1, f"Проведено {count} проверка(ок) за квартал"
    else:
        score, reason = 2, f"Проведено {count} проверок — более одного раза в квартал"
    return CriterionOutcome(
        score=score,
        not_applicable=False,
        missing_input=False,
        fact=f"{count} проверка(ок)",
        threshold=threshold_text,
        reason=reason,
    )


def _evaluate_share_bad(
    criterion: AssessmentCriterion,
    fact: AssessmentFact | None,
    stats: ScopeStats,
) -> CriterionOutcome:
    thresholds = criterion.thresholds
    threshold_text = f"более {thresholds['bad_over']}% — балл 0; {thresholds['mild_from']}–{thresholds['bad_over']}% — балл 1; до {thresholds['mild_from']}% — балл 2"
    if criterion.input_type == "mixed":
        numerator = _int_value(_fact_value(fact, "numerator"))
        if numerator is None:
            return CriterionOutcome(
                score=None,
                not_applicable=False,
                missing_input=True,
                fact=f"Знаменатель из журнала: {stats.total}",
                threshold=threshold_text,
                reason="Введите числитель (число нарушений, не выявленных при предыдущем контуре)",
            )
    else:
        numerator = stats.heavy if "severity_min" in criterion.applicability_rule else stats.repeat
    denominator = stats.total
    score = score_share_bad(numerator, denominator)
    if score is None:
        return CriterionOutcome(
            score=None,
            not_applicable=True,
            missing_input=False,
            fact="Нет данных за период",
            threshold=threshold_text,
            reason="За период нет нарушений соответствующего вида контроля — Н/П",
        )
    share = format_percent(numerator, denominator)
    if score == 2:
        reason = f"Доля {share}% ({numerator} из {denominator}) — менее {thresholds['mild_from']}%"
    elif score == 1:
        reason = f"Доля {share}% ({numerator} из {denominator}) — в диапазоне {thresholds['mild_from']}–{thresholds['bad_over']}%"
    else:
        reason = f"Доля {share}% ({numerator} из {denominator}) — более {thresholds['bad_over']}%"
    return CriterionOutcome(
        score=score,
        not_applicable=False,
        missing_input=False,
        fact=f"{numerator} из {denominator} ({share}%)",
        threshold=threshold_text,
        reason=reason,
    )


def _evaluate_share_on_time_auto(criterion: AssessmentCriterion, stats: ScopeStats) -> CriterionOutcome:
    on_time_from = int(criterion.thresholds["on_time_from"])
    threshold_text = f"менее {on_time_from}% — балл 0; {on_time_from}–99% — балл 1; 100% — балл 2"
    score = score_share_on_time(stats.measures_on_time, stats.measures_arrived)
    if score is None:
        return CriterionOutcome(
            score=None,
            not_applicable=True,
            missing_input=False,
            fact="Нет мероприятий с наступившими сроками",
            threshold=threshold_text,
            reason="За период нет мероприятий с наступившими сроками устранения — Н/П",
        )
    share = format_percent(stats.measures_on_time, stats.measures_arrived)
    reason = f"Устранено в срок {stats.measures_on_time} из {stats.measures_arrived} мер с наступившими сроками ({share}%)"
    return CriterionOutcome(
        score=score,
        not_applicable=False,
        missing_input=False,
        fact=f"{stats.measures_on_time} из {stats.measures_arrived} ({share}%)",
        threshold=threshold_text,
        reason=reason,
    )


def _evaluate_rpo_ratio(
    criterion: AssessmentCriterion, fact: AssessmentFact | None, stats: ScopeStats
) -> CriterionOutcome:
    threshold_text = "менее 0,1 — балл 0; равно 0,1 — балл 1; более 0,1 — балл 2"
    permits = _int_value(_fact_value(fact, "permits"))
    if permits is None:
        return CriterionOutcome(
            score=None,
            not_applicable=False,
            missing_input=True,
            fact=f"Нарушений по типам 1.1 и 5.10: {stats.total}",
            threshold=threshold_text,
            reason="Введите количество выданных нарядов-допусков на РПО",
        )
    numerator = stats.total
    if permits == 0:
        return CriterionOutcome(
            score=None,
            not_applicable=True,
            missing_input=False,
            fact=f"Нарушений: {numerator}; нарядов-допусков: 0",
            threshold=threshold_text,
            reason="Наряды-допуски на РПО отсутствуют — показатель неприменим (Н/П)",
        )
    score = score_rpo_ratio(numerator, permits)
    ratio = numerator / permits
    ratio_text = f"{ratio:.3f}".rstrip("0").rstrip(".")
    if score == 0:
        reason = f"Коэффициент {ratio_text} ({numerator}/{permits}) — менее 0,1"
    elif score == 1:
        reason = f"Коэффициент {ratio_text} ({numerator}/{permits}) — равен 0,1"
    else:
        reason = f"Коэффициент {ratio_text} ({numerator}/{permits}) — более 0,1"
    return CriterionOutcome(
        score=score,
        not_applicable=False,
        missing_input=False,
        fact=f"{numerator} / {permits} = {ratio_text}",
        threshold=threshold_text,
        reason=reason,
    )


def _period_inapplicable_reason(criterion: AssessmentCriterion) -> str | None:
    span = PERIOD_SPANS[criterion.period_type]
    if span == 4:
        return "Годовой критерий — учитывается только в годовой оценке"
    if span == 2:
        return "Критерий полугодия — учитывается начиная с полугодовой оценки"
    return None


def compute_assessment(
    database: Session,
    period_type: str,
    period_year: int,
    period_index: int,
    department_id: UUID | None = None,
) -> AssessmentComputeResponse:
    date_from, date_to = period_bounds(period_type, period_index, period_year)
    assessment_span = PERIOD_SPANS[period_type]
    today = datetime.now(UTC).date()

    department_name = None
    if department_id is not None:
        department = database.get(Department, department_id)
        if department is None:
            raise ValueError("Подразделение не найдено")
        department_name = department.name

    criteria = list(
        database.scalars(
            select(AssessmentCriterion)
            .where(AssessmentCriterion.is_active.is_(True))
            .order_by(AssessmentCriterion.display_order)
        )
    )

    facts: dict[UUID, AssessmentFact] = {}
    subject_key = f"department:{department_id}" if department_id is not None else SERVICE_SUBJECT_KEY
    for fact in database.scalars(
        select(AssessmentFact).where(
            AssessmentFact.period_year == period_year,
            AssessmentFact.period_type == period_type,
            AssessmentFact.period_index == period_index,
            AssessmentFact.subject_key == subject_key,
        )
    ):
        facts[fact.criterion_id] = fact

    stats_cache: dict[tuple, ScopeStats] = {}

    def scoped_stats(rule: dict, subject_type: str) -> ScopeStats:
        cache_key = (tuple(rule.get("control_types", [])), subject_type, department_id, tuple(rule.get("violation_type_codes", []) or []))
        if cache_key not in stats_cache:
            stats_cache[cache_key] = load_scope_stats(
                database,
                date_from,
                date_to,
                list(rule.get("control_types", [])),
                department_id=department_id if subject_type == AssessmentSubjectType.DEPARTMENT else None,
                violation_type_codes=rule.get("violation_type_codes"),
            )
        return stats_cache[cache_key]

    items: list[AssessmentCriterionResult] = []
    scored: list[int] = []
    not_applicable_count = 0
    missing_input_count = 0

    for criterion in criteria:
        base = {
            "criterion_id": criterion.id,
            "criterion_code": criterion.criterion_code,
            "section_code": criterion.section_code,
            "section_title": criterion.section_title,
            "name": criterion.name,
            "subject_type": criterion.subject_type,
            "period_type": criterion.period_type,
            "input_type": criterion.input_type,
            "formula_type": criterion.formula_type,
            "score_mapping": criterion.score_mapping,
            "input_fields": criterion.input_fields,
        }
        fact = facts.get(criterion.id)
        fact_values = dict(fact.values) if fact is not None else {}
        fact_not_applicable = fact is not None and fact.not_applicable
        fact_comment = fact.comment if fact is not None else None

        if criterion.subject_type == AssessmentSubjectType.DEPARTMENT and department_id is None:
            outcome = CriterionOutcome(
                score=None,
                not_applicable=True,
                missing_input=False,
                fact=None,
                threshold=None,
                reason="Не применяется: объект оценки — Служба ППБиБДД, критерий ПК II уровня",
            )
        elif criterion.subject_type == AssessmentSubjectType.SERVICE and department_id is not None:
            outcome = CriterionOutcome(
                score=None,
                not_applicable=True,
                missing_input=False,
                fact=None,
                threshold=None,
                reason="Не применяется: объект оценки — подразделение, критерий ПК III уровня и внешних органов",
            )
        elif PERIOD_SPANS[criterion.period_type] > assessment_span:
            outcome = CriterionOutcome(
                score=None,
                not_applicable=True,
                missing_input=False,
                fact=None,
                threshold=None,
                reason=_period_inapplicable_reason(criterion) or "Не применяется к выбранному периоду",
            )
        elif fact_not_applicable:
            outcome = CriterionOutcome(
                score=None,
                not_applicable=True,
                missing_input=False,
                fact="Помечен как Н/П",
                threshold=None,
                reason="Пользователь пометил критерий как неприменимый",
            )
        else:
            rule = criterion.applicability_rule
            stats = scoped_stats(rule, criterion.subject_type) if rule.get("control_types") else ScopeStats()
            if criterion.formula_type == "report_submission":
                outcome = _evaluate_report_submission(criterion, fact, date_to)
            elif criterion.formula_type == "plan_deadline":
                outcome = _evaluate_plan_deadline(criterion, fact, period_year)
            elif criterion.formula_type == "binary_choice":
                outcome = _evaluate_binary_choice(criterion, fact)
            elif criterion.formula_type == "schedule_deviation":
                outcome = _evaluate_schedule_deviation(criterion, fact)
            elif criterion.formula_type == "share_bad":
                outcome = _evaluate_share_bad(criterion, fact, stats)
            elif criterion.formula_type == "share_on_time":
                outcome = _evaluate_share_on_time_auto(criterion, stats)
            elif criterion.formula_type == "share_on_time_manual":
                outcome = _evaluate_share_on_time_manual(criterion, fact)
            elif criterion.formula_type == "rpo_ratio":
                outcome = _evaluate_rpo_ratio(criterion, fact, stats)
            elif criterion.formula_type == "check_count":
                outcome = _evaluate_check_count(criterion, fact)
            else:
                outcome = CriterionOutcome(
                    score=None,
                    not_applicable=True,
                    missing_input=False,
                    fact=None,
                    threshold=None,
                    reason=f"Неизвестный тип формулы: {criterion.formula_type}",
                )

        items.append(
            AssessmentCriterionResult(
                **base,
                score=outcome.score,
                not_applicable=outcome.not_applicable,
                missing_input=outcome.missing_input,
                fact=outcome.fact,
                threshold=outcome.threshold,
                reason=outcome.reason,
                fact_values=fact_values,
                fact_not_applicable=fact_not_applicable,
                fact_comment=fact_comment,
            )
        )
        if outcome.score is not None:
            scored.append(outcome.score)
        elif outcome.not_applicable:
            not_applicable_count += 1
        else:
            missing_input_count += 1

    average = round(sum(scored) / len(scored), 2) if scored else None
    verdict = None
    if average is not None:
        verdict = VERDICT_SATISFACTORY if average >= 1.0 else VERDICT_UNSATISFACTORY

    return AssessmentComputeResponse(
        period_type=period_type,
        period_year=period_year,
        period_index=period_index,
        period_from=date_from,
        period_to=date_to,
        department_id=department_id,
        department_name=department_name,
        subject_type=AssessmentSubjectType.DEPARTMENT if department_id is not None else AssessmentSubjectType.SERVICE,
        summary=AssessmentSummary(
            applicable_count=len(scored),
            not_applicable_count=not_applicable_count,
            missing_input_count=missing_input_count,
            average_score=average,
            verdict=verdict,
        ),
        criteria=items,
    )


def save_fact(
    database: Session,
    criterion: AssessmentCriterion,
    period_type: str,
    period_year: int,
    period_index: int,
    department_id: UUID | None,
    values: dict,
    not_applicable: bool,
    comment: str | None,
    user_id: UUID,
) -> AssessmentFact:
    if criterion.subject_type == AssessmentSubjectType.DEPARTMENT and department_id is None:
        raise ValueError("Критерий применяется к подразделению — выберите подразделение")
    if criterion.subject_type == AssessmentSubjectType.SERVICE and department_id is not None:
        raise ValueError("Критерий применяется к Службе ППБиБДД — подразделение не указывается")
    subject_type = criterion.subject_type
    subject_key = subject_key_for(subject_type, department_id)

    cleaned_values: dict = {}
    for field in criterion.input_fields:
        key = field["key"]
        if key in values and values[key] is not None:
            cleaned_values[key] = values[key]
    if not_applicable:
        cleaned_values = {}

    fact = database.scalar(
        select(AssessmentFact).where(
            AssessmentFact.criterion_id == criterion.id,
            AssessmentFact.period_year == period_year,
            AssessmentFact.period_type == period_type,
            AssessmentFact.period_index == period_index,
            AssessmentFact.subject_key == subject_key,
        )
    )
    if fact is None:
        fact = AssessmentFact(
            criterion_id=criterion.id,
            period_year=period_year,
            period_type=period_type,
            period_index=period_index,
            subject_type=subject_type,
            department_id=department_id,
            subject_key=subject_key,
            entered_by_id=user_id,
        )
        database.add(fact)
    fact.values = cleaned_values
    fact.not_applicable = not_applicable
    fact.comment = comment
    fact.entered_by_id = user_id
    if fact.department_id is None and department_id is not None:
        fact.department_id = department_id
    return fact
