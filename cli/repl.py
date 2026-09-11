"""交互式和一次性命令执行。"""

import sys

from .banner import HELP_DETAILS, build_welcome


def run(agent, args):
    """运行一次性提示词或交互式 REPL。"""
    print(
        build_welcome(
            agent,
            model=getattr(agent.model_client, "model", "-"),
            host=getattr(agent.model_client, "base_url", "-"),
        )
    )

    if args.prompt:
        prompt = " ".join(args.prompt).strip()
        if prompt:
            print()
            try:
                print(agent.ask(prompt))
            except RuntimeError as exc:
                print(str(exc), file=sys.stderr)
                return 1
        return 0

    while True:
        try:
            user_input = input("\nmini-coding-agent> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("")
            return 0

        if not user_input:
            continue
        if user_input in {"/exit", "/quit"}:
            return 0
        if user_input == "/help":
            print(HELP_DETAILS)
            continue
        if user_input == "/memory":
            print(agent.memory_text())
            continue
        if user_input == "/skills":
            print(agent.list_skills_text())
            continue
        if user_input.startswith("/skill "):
            name = user_input.removeprefix("/skill ").strip()
            if name in {"", "none", "clear", "off"}:
                agent.clear_skill()
                print("active skill cleared")
                continue
            try:
                skill = agent.activate_skill(name)
            except KeyError:
                print(f"unknown skill: {name}")
                continue
            print(f"active skill: {skill.name}")
            continue
        if user_input.startswith("/") and agent.skill_registry is not None:
            name, _, task = user_input[1:].partition(" ")
            if agent.skill_registry.has_skill(name):
                skill = agent.activate_skill(name)
                print(f"active skill: {skill.name}")
                if task.strip():
                    print()
                    try:
                        print(agent.ask(task.strip()))
                    except RuntimeError as exc:
                        print(str(exc), file=sys.stderr)
                continue
        if user_input == "/session":
            print(agent.session_path)
            continue
        if user_input == "/reset":
            agent.reset()
            print("session reset")
            continue

        print()
        try:
            print(agent.ask(user_input))
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
