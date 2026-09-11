import subprocess
import sys
from pathlib import Path

import pytest

from calculator import (
    add,
    calculate,
    clear_history,
    divide,
    get_history,
    multiply,
    subtract,
)


def test_add():
    assert add(2, 3) == 5


def test_subtract():
    assert subtract(5, 3) == 2


def test_multiply():
    assert multiply(4, 3) == 12


def test_divide():
    assert divide(10, 2) == 5


def test_divide_by_zero():
    with pytest.raises(ValueError, match="Cannot divide by zero"):
        divide(10, 0)


def test_calculate_records_history():
    clear_history()

    assert calculate(2, "+", 3) == 5
    assert calculate(10, "-", 4) == 6

    assert get_history() == [
        "2 + 3 = 5",
        "10 - 4 = 6",
    ]


def test_get_history_returns_copy():
    clear_history()
    calculate(2, "*", 3)

    history = get_history()
    history.append("changed")

    assert get_history() == ["2 * 3 = 6"]


def test_clear_history():
    clear_history()

    calculate(8, "/", 2)
    assert get_history() == ["8 / 2 = 4.0"]

    clear_history()

    assert get_history() == []


def test_calculate_rejects_unknown_operator():
    clear_history()

    with pytest.raises(ValueError, match="Unsupported operator"):
        calculate(1, "%", 2)

    assert get_history() == []


def test_cli_addition():
    script = Path(__file__).with_name("calculator.py")

    result = subprocess.run(
        [sys.executable, str(script), "2", "+", "3"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "5.0"
