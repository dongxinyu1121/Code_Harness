"""暴露给模型适配器的工具定义。"""


def response_tool_definitions():
    """以 Responses API 函数工具格式返回 Agent 工具。"""
    fields = {
        "list_files": (
            "List files in the workspace.",
            {"path": {"type": "string", "description": "Directory path."}},
            ["path"],
        ),
        "list_directory_tree": (
            "List a bounded directory tree in the workspace.",
            {
                "path": {"type": "string"},
                "max_depth": {"type": "integer", "default": 3},
                "max_entries": {"type": "integer", "default": 200},
            },
            ["path", "max_depth", "max_entries"],
        ),
        "rename_file": (
            "Rename one file inside the workspace.",
            {"path": {"type": "string"}, "new_path": {"type": "string"}},
            ["path", "new_path"],
        ),
        "delete_file": (
            "Delete one file inside the workspace.",
            {"path": {"type": "string"}},
            ["path"],
        ),
        "read_file": (
            "Read a UTF-8 file by line range.",
            {
                "path": {"type": "string"},
                "start": {"type": "integer", "default": 1},
                "end": {"type": "integer", "default": 200},
            },
            ["path", "start", "end"],
        ),
        "search": (
            "Search the workspace for a text pattern.",
            {
                "pattern": {"type": "string"},
                "path": {"type": "string", "default": "."},
            },
            ["pattern", "path"],
        ),
        "run_shell": (
            "Run a shell command in the workspace.",
            {
                "command": {"type": "string"},
                "timeout": {"type": "integer", "default": 20},
            },
            ["command", "timeout"],
        ),
        "write_file": (
            "Write a text file.",
            {"path": {"type": "string"}, "content": {"type": "string"}},
            ["path", "content"],
        ),
        "patch_file": (
            "Replace one exact text block in a file.",
            {
                "path": {"type": "string"},
                "old_text": {"type": "string"},
                "new_text": {"type": "string"},
            },
            ["path", "old_text", "new_text"],
        ),
        "delegate": (
            "Ask a bounded read-only child agent to investigate.",
            {
                "task": {"type": "string"},
                "max_steps": {"type": "integer", "default": 3},
            },
            ["task", "max_steps"],
        ),
    }
    return [
        {
            "type": "function",
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
            "strict": True,
        }
        for name, (description, properties, required) in fields.items()
    ]
