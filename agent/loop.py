"""The model, tool, observation, and final-answer loop."""

from .termination import step_limit_result


def run(
    *,
    user_message,
    model_client,
    prompt,
    parse,
    run_tool,
    record,
    note_tool,
    remember,
    memory,
    max_steps,
    max_new_tokens,
    clip,
    now,
):
    """Run one agent request until final output or a safety limit."""
    if not memory["task"]:
        memory["task"] = clip(user_message.strip(), 300)
    record({"role": "user", "content": user_message, "created_at": now()})

    tool_steps = 0
    attempts = 0
    max_attempts = max(max_steps * 3, max_steps + 4)

    while tool_steps < max_steps and attempts < max_attempts:
        attempts += 1
        raw = model_client.complete(prompt(user_message), max_new_tokens)
        kind, payload = parse(raw)

        if kind == "tool":
            tool_steps += 1
            name = payload.get("name", "")
            args = payload.get("args", {})
            result = run_tool(name, args)
            submit_tool_result = getattr(model_client, "submit_tool_result", None)
            if submit_tool_result:
                submit_tool_result(result)
            record(
                {
                    "role": "tool",
                    "name": name,
                    "args": args,
                    "content": result,
                    "created_at": now(),
                }
            )
            note_tool(name, args, result)
            continue

        if kind == "retry":
            record({"role": "assistant", "content": payload, "created_at": now()})
            continue

        final = (payload or raw).strip()
        record({"role": "assistant", "content": final, "created_at": now()})
        remember(memory["notes"], clip(final, 220), 5)
        return final

    final = step_limit_result(attempts, tool_steps, max_steps, max_attempts)
    record({"role": "assistant", "content": final, "created_at": now()})
    return final
