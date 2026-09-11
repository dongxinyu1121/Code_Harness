"""用于测试自主编码 Agent 的小型计算器。"""

import sys


_history = []


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


def calculate(left, operator, right):
    """计算结果，并把表达式保存到历史记录中。"""
    operations = {
        "+": add,
        "-": subtract,
        "*": multiply,
        "/": divide,
    }

    if operator not in operations:
        raise ValueError(f"Unsupported operator: {operator}")

    result = operations[operator](left, right)
    _history.append(f"{left} {operator} {right} = {result}")
    return result


def get_history():
    """返回计算历史记录的副本。"""
    return list(_history)


def clear_history():
    """清空计算历史记录。"""
    _history.clear()


def main():
    if len(sys.argv) != 4:
        print("Usage: python calculator.py NUMBER OPERATOR NUMBER")
        return 1

    left = float(sys.argv[1])
    operator = sys.argv[2]
    right = float(sys.argv[3])

    try:
        result = calculate(left, operator, right)
    except ValueError as error:
        print(error)
        return 1

    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
