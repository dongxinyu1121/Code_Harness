"""当前 Agent 循环的终止条件检查。"""


def repeated_tool_call(history, name, args):
    """判断最近两次工具事件是否完全相同。"""
    tool_events = [item for item in history if item["role"] == "tool"]
    if len(tool_events) < 2:
        return False
    recent = tool_events[-2:]
    return all(item["name"] == name and item["args"] == args for item in recent)


def repeated_file_read(history, path):
    """判断文件最近一次写入后是否已经被读取过。"""
    requested = str(path or "").replace("\\", "/").lower()
    if not requested:
        return False
    for item in reversed(history):
        if item.get("role") != "tool":
            continue
        item_path = str(item.get("args", {}).get("path", "")).replace("\\", "/").lower()
        if item["name"] in {"write_file", "patch_file"} and item_path == requested:
            return False
        if item["name"] == "read_file" and item_path == requested:
            return True
    return False


def repeated_observation(history, name, result):
    """判断检查类工具之前是否产生过相同结果。"""
    if name not in {"list_files", "read_file", "search"}:
        return False
    if not result or str(result).startswith("error:"):
        return False
    return any(
        item.get("role") == "tool"
        and item.get("name") == name
        and item.get("content") == result
        for item in history
    )


def step_limit_result(attempts, tool_steps, max_steps, max_attempts):
    """在循环触发安全限制时返回最终消息。"""
    if attempts >= max_attempts and tool_steps < max_steps:
        return "Stopped after too many malformed model responses without a valid tool call or final answer."
    return "Stopped after reaching the step limit without a final answer."
