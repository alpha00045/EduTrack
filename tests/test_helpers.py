import os
import sys
from pathlib import Path

# Ensure the repository root (where app.py lives) is importable when pytest
# is launched from different working directories.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# app.py intentionally requires these settings at import time.
os.environ.setdefault("SECRET_KEY", "test-only-secret-key")
os.environ.setdefault("ADMIN_USERNAME", "test-admin")
os.environ.setdefault("ADMIN_PASSWORD", "test-password")

from werkzeug.datastructures import MultiDict

from app import calculate_average, calculate_grade, safe_spreadsheet_text, validate_student_form


def valid_form(**overrides):
    values = {
        "roll": "101",
        "name": "Asha Das",
        "math": "85",
        "science": "90",
        "english": "88",
    }
    values.update(overrides)
    return MultiDict(values)


def test_validate_student_form_accepts_valid_values():
    data, error = validate_student_form(valid_form())

    assert error is None
    assert data == {
        "roll": 101,
        "name": "Asha Das",
        "math": 85,
        "science": 90,
        "english": 88,
    }


def test_validate_student_form_rejects_blank_name():
    data, error = validate_student_form(valid_form(name="   "))

    assert data is None
    assert "name is required" in error.lower()


def test_validate_student_form_rejects_name_over_100_characters():
    data, error = validate_student_form(valid_form(name="A" * 101))

    assert data is None
    assert "100 characters" in error


def test_validate_student_form_rejects_non_positive_roll():
    for roll in ("0", "-2", "abc"):
        data, error = validate_student_form(valid_form(roll=roll))
        assert data is None
        assert error is not None


def test_validate_student_form_rejects_marks_outside_range():
    for mark in ("-1", "101"):
        data, error = validate_student_form(valid_form(math=mark))
        assert data is None
        assert "between 0 and 100" in error


def test_validate_student_form_rejects_non_integer_marks():
    data, error = validate_student_form(valid_form(science="90.5"))

    assert data is None
    assert "whole number" in error


def test_edit_validation_does_not_require_roll_number():
    data, error = validate_student_form(
        MultiDict({
            "name": "Asha Das",
            "math": "85",
            "science": "90",
            "english": "88",
        }),
        include_roll=False,
    )

    assert error is None
    assert "roll" not in data


def test_calculate_average_ignores_missing_marks():
    assert calculate_average([80, None, 90]) == 85


def test_calculate_average_returns_zero_when_no_marks_exist():
    assert calculate_average([None, None, None]) == 0


def test_calculate_grade_uses_expected_boundaries():
    assert calculate_grade(90) == "A1"
    assert calculate_grade(80) == "A2"
    assert calculate_grade(70) == "B1"
    assert calculate_grade(60) == "B2"
    assert calculate_grade(50) == "C1"
    assert calculate_grade(40) == "C2"
    assert calculate_grade(33) == "D"
    assert calculate_grade(32) == "F"



def test_safe_spreadsheet_text_neutralizes_formula_prefixes():
    for value in ("=1+1", " +1+1", "\t=1+1", "\ufeff@SUM(A1:A2)", "-1+1"):
        assert safe_spreadsheet_text(value) == "'" + value


def test_safe_spreadsheet_text_preserves_ordinary_text_and_numbers():
    assert safe_spreadsheet_text("Asha Das") == "Asha Das"
    assert safe_spreadsheet_text(101) == 101
