"""Stable executable shim for the modular CLI application."""

# Preserve the original public imports while keeping implementation elsewhere.
from agent.runtime import MiniAgent
from cli.app import main
from cli.banner import build_welcome
from memory.session_store import SessionStore
from providers.fake import FakeModelClient
from workspace.snapshot import WorkspaceContext

__all__ = [
    "FakeModelClient",
    "MiniAgent",
    "SessionStore",
    "WorkspaceContext",
    "build_welcome",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
