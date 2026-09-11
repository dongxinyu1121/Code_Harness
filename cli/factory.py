"""应用依赖组装。"""

import os
from pathlib import Path

from agent.runtime import MiniAgent
from memory.session_store import SessionStore
from providers.anthropic_compatible import AnthropicCompatibleProvider
from providers.openai_compatible import OpenAICompatibleProvider
from skills import SkillRegistry, SkillRouter
from tools.registry import response_tool_definitions
from workspace.snapshot import WorkspaceContext


def build_agent(args):
    """组装工作区、模型提供方、会话和 Agent 运行时。"""
    workspace = WorkspaceContext.build(args.cwd)
    store = SessionStore(Path(workspace.cwd) / ".mini-coding-agent" / "sessions")
    skill_registry = SkillRegistry(Path(__file__).resolve().parents[1] / "skills")
    skill_router = SkillRouter()
    provider = (args.provider or os.getenv("LLM_PROVIDER", "openai")).lower()
    tool_mode = (args.tool_mode or os.getenv("LLM_TOOL_MODE", "native")).lower()
    if tool_mode not in {"native", "prompt"}:
        raise ValueError("LLM_TOOL_MODE must be 'native' or 'prompt'")
    model_tools = response_tool_definitions() if tool_mode == "native" else []
    instructions = (
        "You are a coding agent with real workspace tools. "
        + (
            "You MUST use the provided function tools to inspect or modify files. "
            if tool_mode == "native"
            else "Use the XML tool format described in the prompt to inspect or modify files. "
        )
        + "Never claim that tools are unavailable. After receiving a tool result, "
        "use that result and choose the next necessary tool or return a final answer."
    )
    if provider == "anthropic":
        model = AnthropicCompatibleProvider(
            model=args.model or os.getenv("ANTHROPIC_MODEL") or os.getenv("LLM_MODEL"),
            base_url=args.base_url or os.getenv("ANTHROPIC_BASE_URL"),
            api_key=args.api_key or os.getenv("ANTHROPIC_AUTH_TOKEN") or os.getenv("ANTHROPIC_API_KEY"),
            tools=model_tools,
            instructions=instructions,
            timeout=args.timeout,
        )
    else:
        model = OpenAICompatibleProvider(
            model=args.model or os.getenv("LLM_MODEL"),
            base_url=args.base_url or os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL"),
            api_key=args.api_key or os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY"),
            wire_api=args.wire_api or os.getenv("LLM_WIRE_API", "chat_completions"),
            tools=model_tools,
            instructions=instructions,
            temperature=args.temperature,
            top_p=args.top_p,
            timeout=args.timeout,
        )
    session_id = args.resume
    if session_id == "latest":
        session_id = store.latest()
    if session_id:
        return MiniAgent.from_session(
            model_client=model,
            workspace=workspace,
            session_store=store,
            session_id=session_id,
            approval_policy=args.approval,
            max_steps=args.max_steps,
            max_new_tokens=args.max_new_tokens,
            skill_registry=skill_registry,
            skill_router=skill_router,
        )
    return MiniAgent(
        model_client=model,
        workspace=workspace,
        session_store=store,
        approval_policy=args.approval,
        max_steps=args.max_steps,
        max_new_tokens=args.max_new_tokens,
        skill_registry=skill_registry,
        skill_router=skill_router,
    )
