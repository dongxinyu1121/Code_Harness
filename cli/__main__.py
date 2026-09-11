"""允许模块化 CLI 通过 ``python -m cli`` 运行。"""

from .app import main


if __name__ == "__main__":
    raise SystemExit(main())
