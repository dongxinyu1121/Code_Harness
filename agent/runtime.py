"""Agent 核心运行时及其小型兼容接口。"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from agent import loop as agent_loop
from agent import termination
from agent.response_parser import ResponseParser
from memory.session_store import SessionStore
from tools import delegate as delegate_tool
from tools import filesystem as filesystem_tools
from tools import search as search_tool
from tools import shell as shell_tool
from tools import WorkspacePathPolicy


MAX_TOOL_OUTPUT = 12000
MAX_HISTORY = 36000


def now():
    return datetime.now(timezone.utc).isoformat()


def clip(text, limit=MAX_TOOL_OUTPUT):
    text = str(text)
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n...[truncated {len(text) - limit} chars]"


class MiniAgent:
    """协调提示词构建、工具、记忆和 Agent 循环。"""

    def __init__(
        self,
        model_client,
        workspace,
        session_store,
        session=None,
        approval_policy="ask",
        max_steps=18,
        max_new_tokens=1536,
        depth=0,
        max_depth=1,
        read_only=False,
    ):
        self.model_client = model_client
        self.workspace = workspace
        self.root = Path(workspace.cwd)
        self.path_policy = WorkspacePathPolicy(self.root)
        self.session_store = session_store
        self.approval_policy = approval_policy
        self.max_steps = max_steps
        self.max_new_tokens = max_new_tokens
        self.depth = depth
        self.max_depth = max_depth
        self.read_only = read_only
        self.session = session or {
            "id": datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6],
            "created_at": now(),
            "workspace_root": workspace.cwd,
            "history": [],
            "memory": {"task": "", "files": [], "notes": []},
        }
        self.tools = self.build_tools()
        self.prefix = self.build_prefix()
        self.session_path = self.session_store.save(self.session)

    @classmethod
    def from_session(cls, model_client, workspace, session_store, session_id, **kwargs):
        return cls(
            model_client=model_client,
            workspace=workspace,
            session_store=session_store,
            session=session_store.load(session_id),
            **kwargs,
        )

    @staticmethod
    def remember(bucket, item, limit):
        if not item:
            return
        if item in bucket:
            bucket.remove(item)
        bucket.append(item)
        del bucket[:-limit]

    def build_tools(self):
        tools = {
            "list_files": {
                "schema": {"path": "str='.'"},
                "risky": False,
                "description": "List files in the workspace.",
                "run": self.tool_list_files,
            },
            "list_directory_tree": {
                "schema": {
                    "path": "str='.'",
                    "max_depth": "int=3",
                    "max_entries": "int=200",
                },
                "risky": False,
                "description": "List a bounded directory tree.",
                "run": self.tool_list_directory_tree,
            },
            "rename_file": {
                "schema": {"path": "str", "new_path": "str"},
                "risky": True,
                "description": "Rename one file inside the workspace.",
                "run": self.tool_rename_file,
            },
            "delete_file": {
                "schema": {"path": "str"},
                "risky": True,
                "description": "Delete one file inside the workspace.",
                "run": self.tool_delete_file,
            },
            "read_file": {
                "schema": {"path": "str", "start": "int=1", "end": "int=200"},
                "risky": False,
                "description": "Read a UTF-8 file by line range.",
                "run": self.tool_read_file,
            },
            "search": {
                "schema": {"pattern": "str", "path": "str='.'"},
                "risky": False,
                "description": "Search the workspace with rg or a simple fallback.",
                "run": self.tool_search,
            },
            "run_shell": {
                "schema": {"command": "str", "timeout": "int=60"},
                "risky": True,
                "description": "Run a shell command in the repo root.",
                "run": self.tool_run_shell,
            },
            "write_file": {
                "schema": {"path": "str", "content": "str"},
                "risky": True,
                "description": "Write a text file.",
                "run": self.tool_write_file,
            },
            "patch_file": {
                "schema": {"path": "str", "old_text": "str", "new_text": "str"},
                "risky": True,
                "description": "Replace one exact text block in a file.",
                "run": self.tool_patch_file,
            },
        }
        if self.depth < self.max_depth:
            tools["delegate"] = {
                "schema": {"task": "str", "max_steps": "int=9"},
                "risky": False,
                "description": "Ask a bounded read-only child agent to investigate.",
                "run": self.tool_delegate,
            }
        return tools

    def build_prefix(self):
        tool_lines = []
        for name, tool in self.tools.items():
            fields = ", ".join(f"{key}: {value}" for key, value in tool["schema"].items())
            risk = "approval required" if tool["risky"] else "safe"
            tool_lines.append(f"- {name}({fields}) [{risk}] {tool['description']}")
        tool_text = "\n".join(tool_lines)
        examples = "\n".join(
            [
                '<tool>{"name":"list_files","args":{"path":"."}}</tool>',
                '<tool>{"name":"list_directory_tree","args":{"path":".","max_depth":3,"max_entries":200}}</tool>',
                '<tool>{"name":"rename_file","args":{"path":"old.txt","new_path":"new.txt"}}</tool>',
                '<tool>{"name":"delete_file","args":{"path":"temporary.txt"}}</tool>',
                '<tool>{"name":"read_file","args":{"path":"README.md","start":1,"end":80}}</tool>',
                '<tool name="write_file" path="binary_search.py"><content>def binary_search(nums, target):\n    return -1\n</content></tool>',
                '<tool name="patch_file" path="binary_search.py"><old_text>return -1</old_text><new_text>return mid</new_text></tool>',
                '<tool>{"name":"run_shell","args":{"command":"uv run --with pytest python -m pytest -q","timeout":60}}</tool>',
                "<final>Done.</final>",
            ]
        )
        rules = "\n".join(
            [
                "- Use tools instead of guessing about the workspace.",
                "- Return exactly one <tool>...</tool> or one <final>...</final>.",
                "- Tool calls must look like:",
                '  <tool>{"name":"tool_name","args":{...}}</tool>',
                "- For write_file and patch_file with multi-line text, prefer XML style:",
                '  <tool name="write_file" path="file.py"><content>...</content></tool>',
                "- Final answers must look like:",
                "  <final>your answer</final>",
                "- Never invent tool results.",
                "- Treat an unchanged inspection result as no progress. Do not repeat list_files, read_file, or search unless the relevant file or workspace changed.",
                "- Keep answers concise and concrete.",
                "- If the user asks you to create or update a specific file and the path is clear, use write_file or patch_file instead of repeatedly listing files.",
                "- Before writing tests for existing code, read the implementation first.",
                "- When writing tests, match the current implementation unless the user explicitly asked you to change the code.",
                "- New files should be complete and runnable, including obvious imports.",
                "- Do not repeat the same tool call with the same arguments if it did not help. Choose a different tool or return a final answer.",
                "- Required tool arguments must not be empty. Do not call read_file, write_file, patch_file, run_shell, or delegate with args={}.",
            ]
        )
        return "\n\n".join(
            [
                "You are Mini-Coding-Agent, a small local coding agent using an OpenAI-compatible API provider.",
                "Rules:\n" + rules,
                "Tools:\n" + tool_text,
                "Valid response examples:\n" + examples,
                self.workspace.text(),
            ]
        )

    def memory_text(self):
        memory = self.session["memory"]
        notes = "\n".join(f"- {note}" for note in memory["notes"]) or "- none"
        return "\n".join(
            [
                "Memory:",
                f"- task: {memory['task'] or '-'}",
                f"- files: {', '.join(memory['files']) or '-'}",
                "- notes:",
                notes,
            ]
        )

    def history_text(self):
        history = self.session["history"]
        if not history:
            return "- empty"

        lines = []
        seen_reads = set()
        recent_start = max(0, len(history) - 6)
        for index, item in enumerate(history):
            recent = index >= recent_start
            if item["role"] == "tool" and item["name"] in ("write_file", "patch_file"):
                path = str(item["args"].get("path", ""))
                seen_reads.discard(path)
            if item["role"] == "tool" and item["name"] == "read_file" and not recent:
                path = str(item["args"].get("path", ""))
                if path in seen_reads:
                    continue
                seen_reads.add(path)

            if item["role"] == "tool":
                limit = 900 if recent else 180
                lines.append(f"[tool:{item['name']}] {json.dumps(item['args'], sort_keys=True)}")
                lines.append(clip(item["content"], limit))
            else:
                limit = 900 if recent else 220
                lines.append(f"[{item['role']}] {clip(item['content'], limit)}")

        return clip("\n".join(lines), MAX_HISTORY)

    def prompt(self, user_message):
        return "\n\n".join(
            [
                self.prefix,
                self.memory_text(),
                "Transcript:\n" + self.history_text(),
                "Current user request:\n" + user_message,
            ]
        )

    def record(self, item):
        self.session["history"].append(item)
        self.session_path = self.session_store.save(self.session)

    def note_tool(self, name, args, result):
        memory = self.session["memory"]
        path = args.get("path")
        if name in {"read_file", "write_file", "patch_file"} and path:
            self.remember(memory["files"], str(path), 8)
        note = f"{name}: {clip(str(result).replace(chr(10), ' '), 220)}"
        self.remember(memory["notes"], note, 5)

    def ask(self, user_message):
        return agent_loop.run(
            user_message=user_message,
            model_client=self.model_client,
            prompt=self.prompt,
            parse=self.parse,
            run_tool=self.run_tool,
            record=self.record,
            note_tool=self.note_tool,
            remember=self.remember,
            memory=self.session["memory"],
            max_steps=self.max_steps,
            max_new_tokens=self.max_new_tokens,
            clip=clip,
            now=now,
        )

    def run_tool(self, name, args):
        tool = self.tools.get(name)
        if tool is None:
            return f"error: unknown tool '{name}'"
        try:
            self.validate_tool(name, args)
        except Exception as exc:
            example = self.tool_example(name)
            message = f"error: invalid arguments for {name}: {exc}"
            if example:
                message += f"\nexample: {example}"
            return message
        if name == "read_file" and termination.repeated_file_read(
            self.session["history"], args.get("path")
        ):
            return (
                f"error: file already read without a later write: {args.get('path')}; "
                "use the existing result or choose a different tool"
            )
        if self.repeated_tool_call(name, args):
            return f"error: repeated identical tool call for {name}; choose a different tool or return a final answer"
        if tool["risky"] and not self.approve(name, args):
            return f"error: approval denied for {name}"
        try:
            result = clip(tool["run"](args))
            if termination.repeated_observation(self.session["history"], name, result):
                return (
                    f"error: {name} returned the same observation as before; "
                    "use the existing result and choose a different tool or return a final answer"
                )
            return result
        except Exception as exc:
            return f"error: tool {name} failed: {exc}"

    def repeated_tool_call(self, name, args):
        return termination.repeated_tool_call(self.session["history"], name, args)

    def tool_example(self, name):
        examples = {
            "list_files": '<tool>{"name":"list_files","args":{"path":"."}}</tool>',
            "read_file": '<tool>{"name":"read_file","args":{"path":"README.md","start":1,"end":80}}</tool>',
            "search": '<tool>{"name":"search","args":{"pattern":"binary_search","path":"."}}</tool>',
            "run_shell": '<tool>{"name":"run_shell","args":{"command":"uv run --with pytest python -m pytest -q","timeout":60}}</tool>',
            "write_file": '<tool name="write_file" path="binary_search.py"><content>def binary_search(nums, target):\n    return -1\n</content></tool>',
            "patch_file": '<tool name="patch_file" path="binary_search.py"><old_text>return -1</old_text><new_text>return mid</new_text></tool>',
            "delegate": '<tool>{"name":"delegate","args":{"task":"inspect README.md","max_steps":3}}</tool>',
        }
        return examples.get(name, "")

    def validate_tool(self, name, args):
        args = args or {}

        if name == "list_files":
            path = self.path(args.get("path", "."))
            if not path.is_dir():
                raise ValueError("path is not a directory")
            return

        if name == "list_directory_tree":
            path = self.path(args.get("path", "."))
            if not path.is_dir():
                raise ValueError("path is not a directory")
            max_depth = int(args.get("max_depth", 3))
            max_entries = int(args.get("max_entries", 200))
            if max_depth < 0 or max_depth > 10:
                raise ValueError("max_depth must be in [0, 10]")
            if max_entries < 1 or max_entries > 1000:
                raise ValueError("max_entries must be in [1, 1000]")
            return

        if name == "rename_file":
            source = self.path(args["path"])
            destination = self.path(args["new_path"])
            if not source.is_file():
                raise ValueError("source path is not a file")
            if destination.exists():
                raise ValueError("destination already exists")
            return

        if name == "delete_file":
            path = self.path(args["path"])
            if not path.is_file():
                raise ValueError("path is not a file")
            return

        if name == "read_file":
            path = self.path(args["path"])
            if not path.is_file():
                raise ValueError("path is not a file")
            start = int(args.get("start", 1))
            end = int(args.get("end", 200))
            if start < 1 or end < start:
                raise ValueError("invalid line range")
            return

        if name == "search":
            pattern = str(args.get("pattern", "")).strip()
            if not pattern:
                raise ValueError("pattern must not be empty")
            self.path(args.get("path", "."))
            return

        if name == "run_shell":
            command = str(args.get("command", "")).strip()
            if not command:
                raise ValueError("command must not be empty")
            timeout = int(args.get("timeout", 60))
            if timeout < 1 or timeout > 360:
                raise ValueError("timeout must be in [1, 120]")
            return

        if name == "write_file":
            path = self.path(args["path"])
            if path.exists() and path.is_dir():
                raise ValueError("path is a directory")
            if "content" not in args:
                raise ValueError("missing content")
            return

        if name == "patch_file":
            path = self.path(args["path"])
            if not path.is_file():
                raise ValueError("path is not a file")
            old_text = str(args.get("old_text", ""))
            if not old_text:
                raise ValueError("old_text must not be empty")
            if "new_text" not in args:
                raise ValueError("missing new_text")
            text = path.read_text(encoding="utf-8")
            count = text.count(old_text)
            if count != 1:
                raise ValueError(f"old_text must occur exactly once, found {count}")
            return

        if name == "delegate":
            if self.depth >= self.max_depth:
                raise ValueError("delegate depth exceeded")
            task = str(args.get("task", "")).strip()
            if not task:
                raise ValueError("task must not be empty")

    def approve(self, name, args):
        if self.read_only:
            return False
        if self.approval_policy == "auto":
            return True
        if self.approval_policy == "never":
            return False
        try:
            answer = input(f"approve {name} {json.dumps(args, ensure_ascii=True)}? [y/N] ")
        except EOFError:
            return False
        return answer.strip().lower() in {"y", "yes"}

    @staticmethod
    def parse(raw):
        return ResponseParser.parse(raw)

    @staticmethod
    def retry_notice(problem=None):
        return ResponseParser.retry_notice(problem)

    @staticmethod
    def parse_xml_tool(raw):
        return ResponseParser.parse_xml_tool(raw)

    @staticmethod
    def parse_attrs(text):
        return ResponseParser.parse_attrs(text)

    @staticmethod
    def extract(text, tag):
        return ResponseParser.extract(text, tag)

    @staticmethod
    def extract_raw(text, tag):
        return ResponseParser.extract_raw(text, tag)

    def reset(self):
        self.session["history"] = []
        self.session["memory"] = {"task": "", "files": [], "notes": []}
        self.session_store.save(self.session)

    def path_is_within_root(self, resolved):
        return self.path_policy.path_is_within_root(resolved)

    def path(self, raw_path):
        return self.path_policy.resolve(raw_path)

    def tool_list_files(self, args):
        return filesystem_tools.list_files(self.root, self.path_policy, args)

    def tool_list_directory_tree(self, args):
        return filesystem_tools.list_directory_tree(self.root, self.path_policy, args)

    def tool_rename_file(self, args):
        return filesystem_tools.rename_file(self.root, self.path_policy, args)

    def tool_delete_file(self, args):
        return filesystem_tools.delete_file(self.root, self.path_policy, args)

    def tool_read_file(self, args):
        return filesystem_tools.read_file(self.root, self.path_policy, args)

    def tool_search(self, args):
        return search_tool.search(self.root, self.path_policy, args)

    def tool_run_shell(self, args):
        return shell_tool.run_shell(self.root, args)

    def tool_write_file(self, args):
        return filesystem_tools.write_file(self.root, self.path_policy, args)

    def tool_patch_file(self, args):
        return filesystem_tools.patch_file(self.root, self.path_policy, args)

    def tool_delegate(self, args):
        if self.depth >= self.max_depth:
            raise ValueError("delegate depth exceeded")

        def create_child_agent(child_args):
            return MiniAgent(
                model_client=self.model_client,
                workspace=self.workspace,
                session_store=self.session_store,
                approval_policy="never",
                max_steps=int(child_args.get("max_steps", 3)),
                max_new_tokens=self.max_new_tokens,
                depth=self.depth + 1,
                max_depth=self.max_depth,
                read_only=True,
            )

        return delegate_tool.delegate(args, create_child_agent, self.history_text, clip)
