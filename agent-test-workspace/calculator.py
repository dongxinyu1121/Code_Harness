"""A tiny calculator used to test an autonomous coding agent."""

import sys


def add(left, right):
    return left + right


def subtract(left, right):
    return left - right


def multiply(left, right):
    return left * right


def divide(left, right):
    if right == 0:
        raise ValueError("Cannot divide by zero")
    return left / right


def main():
    if len(sys.argv) != 4:
        print("Usage: python calculator.py NUMBER OPERATOR NUMBER")
        return 1

    left = float(sys.argv[1])
    operator = sys.argv[2]
    right = float(sys.argv[3])

    operations = {
        "+": add,
        "-": subtract,
        "*": multiply,
        "/": divide,
    }

    if operator not in operations:
        print(f"Unsupported operator: {operator}")
        return 1

    result = operations[operator](left, right)
    print(f"{result:g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
