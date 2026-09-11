"""CLI 配置和环境变量加载。"""

import argparse
import os
from pathlib import Path


HELP_TEXT = "/help, /memory, /skills, /skill, /session, /reset, /exit"


def load_local_env(path=".env"):
    """从本地 dotenv 文件加载简单的 KEY=VALUE 配置。"""
    env_path = Path(path)
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key:
            os.environ[key] = value


def build_arg_parser():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="Minimal coding agent for OpenAI-compatible API providers.",
    )
    parser.add_argument("prompt", nargs="*", help="Optional one-shot prompt.")
    parser.add_argument("--cwd", default=".", help="Workspace directory.")
    parser.add_argument(
        "--provider",
        choices=("openai", "anthropic"),
        default=None,
        help="Provider protocol; defaults to LLM_PROVIDER.",
    )
    parser.add_argument("--model", default=None, help="Model name; defaults to LLM_MODEL.")
    parser.add_argument("--base-url", default=None, help="API base URL; defaults to LLM_BASE_URL.")
    parser.add_argument("--api-key", default=None, help="API key; defaults to LLM_API_KEY.")
    parser.add_argument(
        "--wire-api",
        choices=("chat_completions", "responses"),
        default=None,
        help="OpenAI-compatible wire protocol; defaults to LLM_WIRE_API.",
    )
    parser.add_argument(
        "--tool-mode",
        choices=("native", "prompt"),
        default=None,
        help="Use native API tools or prompt/XML tools; defaults to LLM_TOOL_MODE.",
    )
    parser.add_argument("--timeout", type=int, default=900, help="API request timeout in seconds.")
    parser.add_argument("--resume", default=None, help="Session id to resume or 'latest'.")
    parser.add_argument(
        "--approval",
        choices=("ask", "auto", "never"),
        default="auto",
        help="Approval policy for risky tools; auto grants the model arbitrary command execution and file writes.",
    )
    parser.add_argument("--max-steps", type=int, default=18, help="Maximum tool/model iterations per request.")
    parser.add_argument("--max-new-tokens", type=int, default=1536, help="Maximum model output tokens per step.")
    parser.add_argument("--temperature", type=float, default=0.2, help="Sampling temperature.")
    parser.add_argument("--top-p", type=float, default=0.9, help="Top-p sampling value.")
    return parser
