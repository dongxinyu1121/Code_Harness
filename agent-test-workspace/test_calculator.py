from calculator import add, divide, multiply, subtract
import subprocess
import sys

import pytest


def test_add():
    assert add(2, 3) == 5


def test_subtract():
    assert subtract(8, 3) == 5


def test_multiply():
    assert multiply(4, 3) == 12


def test_divide():
    assert divide(8, 2) == 4


def test_divide_by_zero():
    with pytest.raises(ValueError):
        divide(8, 0)


def test_cli_divide():
    result = subprocess.run(
        [sys.executable, "calculator.py", "8", "/", "2"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "4"
