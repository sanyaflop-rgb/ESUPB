from datetime import date
from uuid import uuid4

from app.services.imports import (
    parse_date_value,
    parse_responsible,
    person_key,
    preview_rows,
    resolve_responsibles,
    suggest_mapping,
)


def test_parse_responsible_extracts_position_and_name() -> None:
    parsed = parse_responsible("Начальник производства №2 | Галеев К.Р.")
    assert parsed["name"] == "Галеев К.Р."
    assert parsed["position"] == "Начальник производства №2"

    inline = parse_responsible("Начальник Производства № 4 Паршев А.С.")
    assert inline["name"] == "Паршев А.С."
    assert inline["position"] == "Начальник Производства № 4"


def test_parse_responsible_keeps_position_without_name() -> None:
    parsed = parse_responsible("Начальник цеха водоснабжения и водоотведения")
    assert parsed["name"] is None
    assert parsed["position"] == "Начальник цеха водоснабжения и водоотведения"
    assert parse_responsible("") == {"name": None, "position": None}


def test_person_key_normalizes_initials_and_full_names() -> None:
    assert person_key("Иванов Иван Иванович") == person_key("Иванов И.И.")
    assert person_key("Иванов Иван Иванович") == ("иванов", "ИИ")
    assert person_key("Галеев Кирилл Равильевич") == ("галеев", "КР")
    assert person_key("Петров Пётр Петрович") == ("петров", "ПП")
    assert person_key("Петров") is None


def test_resolve_responsibles_matches_by_surname_and_initials() -> None:
    person_id = uuid4()
    rows: list[dict[str, object]] = [
        {"row_number": 1, "values": {"Ответственный": "Начальник установки Иванов И.И."}},
        {"row_number": 2, "values": {"Ответственный": "Начальник производства №2 Галеев К.Р."}},
        {"row_number": 3, "values": {"Ответственный": ""}},
    ]
    resolve_responsibles(rows, {"responsible": "Ответственный"}, [(person_id, "Иванов Иван Иванович")])
    first = rows[0]["responsible"]
    assert first["person_id"] == person_id
    assert first["person_name"] == "Иванов Иван Иванович"
    assert first["name"] == "Иванов И.И."
    second = rows[1]["responsible"]
    assert second["name"] == "Галеев К.Р."
    assert second["person_id"] is None
    assert rows[2]["responsible"] is None


def test_resolve_responsibles_without_mapped_column_leaves_rows_empty() -> None:
    rows: list[dict[str, object]] = [{"row_number": 1, "values": {"Нарушение": "Текст"}}]
    resolve_responsibles(rows, {}, [])
    assert rows[0]["responsible"] is None


def test_preview_rows_skips_numbering_and_extracts_due_date() -> None:
    headers = ["№", "Нарушение", "Мероприятие", "Ответственный"]
    rows = [
        ["1", "2", "3", "4"],
        ["1", "Нарушение А", "Срок: 25.09.2026", "Иванов И.И."],
    ]
    mapping, preview = preview_rows(headers, rows, {})
    assert mapping["formulation"] == "Нарушение"
    assert mapping["measure"] == "Мероприятие"
    assert mapping["responsible"] == "Ответственный"
    assert len(preview) == 1
    assert preview[0]["due_date"] == date(2026, 9, 25)
    assert preview[0]["errors"] == []


def test_suggest_mapping_for_plain_headers() -> None:
    headers = ["Формулировка", "Мероприятие", "Ответственный", "Срок"]
    mapping = suggest_mapping(headers, {})
    assert mapping["formulation"] == "Формулировка"
    assert mapping["requirement"] == "Формулировка"
    assert mapping["measure"] == "Мероприятие"
    assert mapping["responsible"] == "Ответственный"
    assert mapping["due_date"] == "Срок"


def test_suggest_mapping_separates_requirement_and_due_columns() -> None:
    headers = ["№", "Выявленные нарушения", "Требование", "Мероприятие", "Ответственный", "Срок устранения"]
    mapping = suggest_mapping(headers, {})
    assert mapping["formulation"] == "Выявленные нарушения"
    assert mapping["requirement"] == "Требование"
    assert mapping["measure"] == "Мероприятие"
    assert mapping["responsible"] == "Ответственный"
    assert mapping["due_date"] == "Срок устранения"


def test_suggest_mapping_for_act_headers_with_embedded_due_date() -> None:
    headers = [
        "№ п/п",
        "Выявленные несоответствия (нарушения) с указанием нормативного документа, требования которого нарушено и/ или не соблюдено",
        "Предлагаемые меры и срок устранения несоответствия (нарушения)",
        "Ответственный за устранение несоответствия (нарушения)",
    ]
    mapping = suggest_mapping(headers, {})
    assert mapping["formulation"] == headers[1]
    assert mapping["requirement"] == headers[1]
    assert mapping["measure"] == headers[2]
    assert mapping["responsible"] == headers[3]
    assert "due_date" not in mapping


def test_suggest_mapping_keeps_supplied_headers() -> None:
    headers = ["Формулировка", "Мероприятие", "Ответственный", "Срок"]
    mapping = suggest_mapping(headers, {"formulation": "Мероприятие", "measure": "Ответственный"})
    assert mapping["formulation"] == "Мероприятие"
    assert mapping["measure"] == "Ответственный"
    assert mapping["responsible"] == "Ответственный"


def test_parse_date_value_tolerates_prefixes_and_suffixes() -> None:
    assert parse_date_value("30.10.2026") == date(2026, 10, 30)
    assert parse_date_value("до 30.10.2026 г.") == date(2026, 10, 30)
    assert parse_date_value("30/10/26") == date(2026, 10, 30)
    assert parse_date_value("3 дня") is None


def test_preview_rows_uses_due_date_column_before_measure_text() -> None:
    headers = ["Формулировка", "Мероприятие", "Ответственный", "Срок"]
    rows = [["Нарушение А", "Мероприятие А", "Иванов И.И.", "до 30.10.2026"]]
    mapping, preview = preview_rows(headers, rows, {})
    assert mapping["due_date"] == "Срок"
    assert preview[0]["due_date"] == date(2026, 10, 30)
    assert preview[0]["errors"] == []
    rows_bad = [["Нарушение А", "Мероприятие А срок: 01.11.2026", "Иванов И.И.", "3 дня"]]
    _, preview_bad = preview_rows(headers, rows_bad, {})
    assert preview_bad[0]["due_date"] == date(2026, 11, 1)
