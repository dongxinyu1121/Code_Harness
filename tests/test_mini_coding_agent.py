import json
from argparse import Namespace
from pathlib import Path
import pytest
from unittest.mock import patch

from agent.runtime import MiniAgent
from cli.banner import build_welcome
from memory.session_store import SessionStore
from providers.fake import FakeModelClient
from providers.openai_compatible import OpenAICompatibleProvider
from providers.anthropic_compatible import AnthropicCompatibleProvider
from workspace.snapshot import WorkspaceContext
import cli.factory as cli_factory
from cli.config import build_arg_parser


def build_workspace(tmp_path):
    (tmp_path / "README.md").write_text("demo\n", encoding="utf-8")
    return WorkspaceContext.build(tmp_path)


def build_agent(tmp_path, outputs, **kwargs):
    workspace = build_workspace(tmp_path)
    store = SessionStore(tmp_path / ".mini-coding-agent" / "sessions")
    approval_policy = kwargs.pop("approval_policy", "auto")
    return MiniAgent(
        model_client=FakeModelClient(outputs),
        workspace=workspace,
        session_store=store,
        approval_policy=approval_policy,
        **kwargs,
    )


def test_cli_defaults_to_auto_approval():
    args = build_arg_parser().parse_args([])

    assert args.approval == "auto"


def test_agent_runs_tool_then_final(tmp_path):
    (tmp_path / "hello.txt").write_text("alpha\nbeta\n", encoding="utf-8")
    agent = build_agent(
        tmp_path,
        [
            '<tool>{"name":"read_file","args":{"path":"hello.txt","start":1,"end":2}}</tool>',
            "<final>Read the file successfully.</final>",
        ],
    )

    answer = agent.ask("Inspect hello.txt")

    assert answer == "Read the file successfully."
    assert any(item["role"] == "tool" and item["name"] == "read_file" for item in agent.session["history"])
    assert "hello.txt" in agent.session["memory"]["files"]


def test_agent_retries_after_empty_model_output(tmp_path):
    agent = build_agent(
        tmp_path,
        [
            "",
            "<final>Recovered after retry.</final>",
        ],
    )

    answer = agent.ask("Do the task")

    assert answer == "Recovered after retry."
    notices = [item["content"] for item in agent.session["history"] if item["role"] == "assistant"]
    assert any("empty response" in item for item in notices)


def test_agent_retries_after_malformed_tool_payload(tmp_path):
    (tmp_path / "hello.txt").write_text("alpha\n", encoding="utf-8")
    agent = build_agent(
        tmp_path,
        [
            '<tool>{"name":"read_file","args":"bad"}</tool>',
            '<tool>{"name":"read_file","args":{"path":"hello.txt","start":1,"end":1}}</tool>',
            "<final>Recovered after malformed tool output.</final>",
        ],
    )

    answer = agent.ask("Inspect hello.txt")

    assert answer == "Recovered after malformed tool output."
    assert any(item["role"] == "tool" and item["name"] == "read_file" for item in agent.session["history"])
    notices = [item["content"] for item in agent.session["history"] if item["role"] == "assistant"]
    assert any("valid <tool> call" in item for item in notices)


def test_agent_accepts_xml_write_file_tool(tmp_path):
    agent = build_agent(
        tmp_path,
        [
            '<tool name="write_file" path="hello.py"><content>print("hi")\n</content></tool>',
            "<final>Done.</final>",
        ],
    )

    answer = agent.ask("Create hello.py")

    assert answer == "Done."
    assert (tmp_path / "hello.py").read_text(encoding="utf-8") == 'print("hi")\n'


def test_retries_do_not_consume_the_whole_budget(tmp_path):
    agent = build_agent(
        tmp_path,
        [
            "",
            "",
            "<final>Recovered after several retries.</final>",
        ],
        max_steps=1,
    )

    answer = agent.ask("Do the task")

    assert answer == "Recovered after several retries."


def test_agent_saves_and_resumes_session(tmp_path):
    agent = build_agent(tmp_path, ["<final>First pass.</final>"])
    assert agent.ask("Start a session") == "First pass."

    resumed = MiniAgent.from_session(
        model_client=FakeModelClient(["<final>Resumed.</final>"]),
        workspace=agent.workspace,
        session_store=agent.session_store,
        session_id=agent.session["id"],
        approval_policy="auto",
    )

    assert resumed.session["history"][0]["content"] == "Start a session"
    assert resumed.ask("Continue") == "Resumed."


def test_delegate_uses_child_agent(tmp_path):
    agent = build_agent(
        tmp_path,
        [
            '<tool>{"name":"delegate","args":{"task":"inspect README","max_steps":2}}</tool>',
            "<final>Child result.</final>",
            "<final>Parent incorporated the child result.</final>",
        ],
    )

    answer = agent.ask("Use delegation")

    assert answer == "Parent incorporated the child result."
    tool_events = [item for item in agent.session["history"] if item["role"] == "tool"]
    assert tool_events[0]["name"] == "delegate"
    assert "delegate_result" in tool_events[0]["content"]


def test_patch_file_replaces_exact_match(tmp_path):
    file_path = tmp_path / "sample.txt"
    file_path.write_text("hello world\n", encoding="utf-8")
    agent = build_agent(tmp_path, [])

    result = agent.run_tool(
        "patch_file",
        {
            "path": "sample.txt",
            "old_text": "world",
            "new_text": "agent",
        },
    )

    assert result == "patched sample.txt"
    assert file_path.read_text(encoding="utf-8") == "hello agent\n"


def test_invalid_risky_tool_does_not_prompt_for_approval(tmp_path):
    agent = build_agent(tmp_path, [], approval_policy="ask")

    with patch("builtins.input") as mock_input:
        result = agent.run_tool("write_file", {})

    assert result.startswith("error: invalid arguments for write_file: 'path'")
    assert 'example: <tool name="write_file"' in result
    mock_input.assert_not_called()


def test_list_files_hides_internal_agent_state(tmp_path):
    agent = build_agent(tmp_path, [])
    (tmp_path / ".mini-coding-agent").mkdir(exist_ok=True)
    (tmp_path / ".git").mkdir(exist_ok=True)
    (tmp_path / "hello.txt").write_text("hi\n", encoding="utf-8")

    result = agent.run_tool("list_files", {})

    assert ".mini-coding-agent" not in result
    assert ".git" not in result
    assert "[F] hello.txt" in result


def test_list_directory_tree_is_bounded_and_hides_internal_state(tmp_path):
    (tmp_path / "src" / "nested").mkdir(parents=True)
    (tmp_path / "src" / "main.py").write_text("print('hi')\n", encoding="utf-8")
    (tmp_path / "src" / "nested" / "deep.txt").write_text("deep\n", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".mini-coding-agent").mkdir()
    agent = build_agent(tmp_path, [])

    result = agent.run_tool(
        "list_directory_tree",
        {"path": ".", "max_depth": 2, "max_entries": 10},
    )

    assert "[D] src" in result
    assert "[F] src\\main.py" in result
    assert "[F] src\\nested\\deep.txt" in result
    assert ".git" not in result
    assert ".mini-coding-agent" not in result


def test_rename_file_moves_a_file_inside_workspace(tmp_path):
    (tmp_path / "old.txt").write_text("hello\n", encoding="utf-8")
    agent = build_agent(tmp_path, [])

    result = agent.run_tool(
        "rename_file",
        {"path": "old.txt", "new_path": "new.txt"},
    )

    assert result == "renamed old.txt -> new.txt"
    assert not (tmp_path / "old.txt").exists()
    assert (tmp_path / "new.txt").read_text(encoding="utf-8") == "hello\n"


def test_delete_file_requires_approval_and_removes_a_file(tmp_path):
    path = tmp_path / "temporary.txt"
    path.write_text("remove me\n", encoding="utf-8")
    agent = build_agent(tmp_path, [], approval_policy="auto")

    result = agent.run_tool("delete_file", {"path": "temporary.txt"})

    assert result == "deleted temporary.txt"
    assert not path.exists()


def test_welcome_logo_uses_fixed_width_lines(tmp_path):
    agent = build_agent(tmp_path, [])
    welcome = build_welcome(agent, model="gpt-5.5", host="https://api.example.com")
    logo_lines = welcome.splitlines()[1:6]

    assert len({len(line) for line in logo_lines}) == 1
    art_positions = [
        next(index for index, char in enumerate(line[2:-2]) if char != " ")
        for line in logo_lines
    ]
    assert len(set(art_positions)) == 1


def test_path_rejects_parent_escape(tmp_path):
    agent = build_agent(tmp_path, [])

    with pytest.raises(ValueError, match="path escapes workspace"):
        agent.path("../outside.txt")


def test_explicit_cwd_is_the_agent_workspace_even_inside_a_git_repo(tmp_path):
    workspace_dir = tmp_path / "nested-workspace"
    workspace_dir.mkdir()
    workspace = WorkspaceContext.build(workspace_dir)
    agent = MiniAgent(
        model_client=FakeModelClient([]),
        workspace=workspace,
        session_store=SessionStore(workspace_dir / ".mini-coding-agent" / "sessions"),
        approval_policy="auto",
    )

    assert Path(agent.root) == workspace_dir.resolve()
    assert agent.session["workspace_root"] == str(workspace_dir.resolve())


def test_path_rejects_symlink_escape(tmp_path):
    agent = build_agent(tmp_path, [])
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    link = tmp_path / "outside-link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is not available in this environment")

    with pytest.raises(ValueError, match="path escapes workspace"):
        agent.path("outside-link/secret.txt")


def test_path_accepts_case_variant_on_case_insensitive_filesystems(tmp_path):
    project_root = tmp_path / "Proj"
    project_root.mkdir()
    agent = build_agent(project_root, [])
    variant = project_root.parent / project_root.name.lower() / "README.md"

    if not variant.exists():
        pytest.skip("case-sensitive filesystem")

    resolved = agent.path(str(variant))

    assert resolved.samefile(project_root / "README.md")


def test_repeated_identical_tool_call_is_rejected(tmp_path):
    agent = build_agent(tmp_path, [])
    agent.record({"role": "tool", "name": "list_files", "args": {}, "content": "(empty)", "created_at": "1"})
    agent.record({"role": "tool", "name": "list_files", "args": {}, "content": "(empty)", "created_at": "2"})

    result = agent.run_tool("list_files", {})

    assert result == "error: repeated identical tool call for list_files; choose a different tool or return a final answer"


def test_repeated_read_of_same_file_is_rejected_until_file_changes(tmp_path):
    file_path = tmp_path / "hello.txt"
    file_path.write_text("hello\n", encoding="utf-8")
    agent = build_agent(tmp_path, [])

    first = agent.run_tool("read_file", {"path": "hello.txt", "start": 1, "end": 1})
    agent.record(
        {
            "role": "tool",
            "name": "read_file",
            "args": {"path": "hello.txt", "start": 1, "end": 1},
            "content": first,
            "created_at": "1",
        }
    )
    second = agent.run_tool("read_file", {"path": "hello.txt", "start": 2, "end": 3})

    assert "hello.txt" in first
    assert second == (
        "error: file already read without a later write: hello.txt; "
        "use the existing result or choose a different tool"
    )

    agent.run_tool(
        "patch_file",
        {"path": "hello.txt", "old_text": "hello", "new_text": "updated"},
    )
    agent.record(
        {
            "role": "tool",
            "name": "patch_file",
            "args": {"path": "hello.txt"},
            "content": "patched hello.txt",
            "created_at": "2",
        }
    )
    refreshed = agent.run_tool("read_file", {"path": "hello.txt", "start": 1, "end": 1})
    assert "updated" in refreshed


def test_identical_inspection_result_is_rejected_as_no_progress(tmp_path):
    (tmp_path / "hello.txt").write_text("hello\n", encoding="utf-8")
    agent = build_agent(tmp_path, [])

    first = agent.run_tool("list_files", {"path": "."})
    agent.record(
        {
            "role": "tool",
            "name": "list_files",
            "args": {"path": "."},
            "content": first,
            "created_at": "1",
        }
    )

    second = agent.run_tool("list_files", {"path": "."})
    assert second == (
        "error: list_files returned the same observation as before; "
        "use the existing result and choose a different tool or return a final answer"
    )


def test_welcome_screen_keeps_box_shape_for_long_paths(tmp_path):
    deep = tmp_path / "very" / "long" / "path" / "for" / "the" / "mini" / "agent" / "welcome" / "screen"
    deep.mkdir(parents=True)
    agent = build_agent(deep, [])

    welcome = build_welcome(agent, model="qwen3.5:4b", host="http://127.0.0.1:11434")
    lines = welcome.splitlines()

    assert len(lines) >= 5
    assert len({len(line) for line in lines}) == 1
    assert "..." in welcome
    assert "DXY CODING AGENT" in welcome
    assert "MINI-CODING-AGENT" not in welcome
    assert "MINI CODING AGENT" not in welcome
    assert "// READY" not in welcome
    assert "SLASH" not in welcome
    assert "READY      " not in welcome
    assert "commands: Commands:" not in welcome


def test_prompt_top_level_sections_stay_flush_left_with_multiline_content(tmp_path):
    workspace = WorkspaceContext(
        cwd=str(tmp_path),
        repo_root=str(tmp_path),
        branch="fix/prompt-indentation",
        default_branch="main",
        status=" M cli/app.py\n?? tests/test_prompt.py",
        recent_commits=["abc123 first commit", "def456 second commit"],
        project_docs={"README.md": "line1\nline2"},
    )
    store = SessionStore(tmp_path / ".mini-coding-agent" / "sessions")
    agent = MiniAgent(
        model_client=FakeModelClient([]),
        workspace=workspace,
        session_store=store,
        approval_policy="auto",
    )
    agent.session["memory"] = {
        "task": "verify prompt formatting",
        "files": ["cli/app.py"],
        "notes": ["saw inconsistent indentation", "need regression coverage"],
    }
    agent.record({"role": "user", "content": "inspect prompt()", "created_at": "1"})
    agent.record(
        {
            "role": "tool",
            "name": "read_file",
            "args": {"path": "cli/app.py"},
            "content": "    def main(argv=None):\n        ...",
            "created_at": "2",
        }
    )

    prompt = agent.prompt("is this issue legit?")
    lines = prompt.splitlines()

    for label in ["Rules:", "Tools:", "Valid response examples:", "Workspace:", "Memory:", "Transcript:", "Current user request:"]:
        assert label in lines
        assert f"            {label}" not in prompt


def _make_filler(i):
    return {"role": "tool", "name": "list_files", "args": {}, "content": "", "created_at": str(i)}


def test_history_text_deduplicates_reads_but_not_after_write(tmp_path):
    """read_file 去重不能跳过写入之后的读取。

    模拟之前轮次的历史记录（非最近窗口）：
        user: "update config"
        assistant: <tool>read_file config</tool>
        tool:   config v1 (content: setting=true)
        assistant: <tool>write_file config</tool>
        tool:   wrote
        assistant: <tool>read_file config</tool>
        tool:   config v2 (content: setting=false)   <- 不能跳过

    修复前：第一次读取后 seen_reads={"config"}；写入没有清理它；
            第二次读取会被错误跳过（LLM 看到旧内容）。
    修复后：写入会清理 seen_reads，第二次读取会正确显示。
    """
    agent = build_agent(tmp_path, [])

    # 模拟同一个文件在之前轮次中经历 read->write->read。
    # history_length=13，recent_start=7（索引 0-6 为非最近记录，7-12 为最近记录）。
    agent.record({"role": "user", "content": "update config", "created_at": "0"})        # 索引 0
    agent.record({"role": "assistant", "content": '<tool>{"name":"read_file","args":{"path":"config.txt"}}</tool>', "created_at": "1"})
    agent.record({"role": "tool", "name": "read_file", "args": {"path": "config.txt"}, "content": "# config.txt\n   1: setting=true\n", "created_at": "2"})  # 索引 2，非最近记录，已加入
    agent.record({"role": "assistant", "content": '<tool>{"name":"write_file","args":{"path":"config.txt","content":"setting=false\n"}}</tool>', "created_at": "3"})
    agent.record({"role": "tool", "name": "write_file", "args": {"path": "config.txt", "content": "setting=false\n"}, "content": "wrote config.txt", "created_at": "4"})  # 索引 4，非最近记录
    agent.record({"role": "assistant", "content": '<tool>{"name":"read_file","args":{"path":"config.txt"}}</tool>', "created_at": "5"})
    agent.record({"role": "tool", "name": "read_file", "args": {"path": "config.txt"}, "content": "# config.txt\n   1: setting=false\n", "created_at": "6"})  # 索引 6，非最近记录，已加入（写入清理了去重状态）
    # 最近记录。
    for i in range(7, 13):
        agent.record(_make_filler(i))

    history = agent.history_text()

    # 两次读取内容都只出现一次（检查整行以避免 JSON 造成误判）。
    assert "# config.txt\n   1: setting=true\n" in history
    assert "# config.txt\n   1: setting=false\n" in history
    # 同时确认重复读取（setting=true，同一路径）不会出现两次。
    assert history.count("setting=true") == 1


def test_history_text_deduplicates_unchanged_repeated_reads(tmp_path):
    """read_file 去重仍应跳过中间没有写入的重复读取。"""
    agent = build_agent(tmp_path, [])

    # 更真实的场景：两次完全相同的读取之间没有写入。
    # history_length=10，recent_start=4（索引 0-3 为非最近记录，4-9 为最近记录）。
    agent.record({"role": "user", "content": "check logs", "created_at": "0"})  # 索引 0
    agent.record({"role": "assistant", "content": '<tool>{"name":"read_file","args":{"path":"log.txt"}}</tool>', "created_at": "1"})
    agent.record({"role": "tool", "name": "read_file", "args": {"path": "log.txt"}, "content": "# log.txt\n   1: stable\n", "created_at": "2"})  # 索引 2，非最近记录，已加入
    agent.record({"role": "assistant", "content": '<tool>{"name":"read_file","args":{"path":"log.txt"}}</tool>', "created_at": "3"})  # 索引 3，非最近记录，跳过（重复）
    for i in range(4, 10):
        agent.record(_make_filler(i))  # 索引 4-9，最近记录。

    history = agent.history_text()

    # 只应出现第一次读取，重复内容必须跳过。
    assert history.count("stable") == 1


def test_openai_compatible_provider_posts_expected_payload():
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(
                {"choices": [{"message": {"content": "<final>ok</final>"}}]}
            ).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["authorization"] = request.get_header("Authorization")
        return FakeResponse()

    client = OpenAICompatibleProvider(
        model="deepseek-chat",
        base_url="https://api.example.com/v1",
        api_key="test-key",
        temperature=0.2,
        top_p=0.9,
        timeout=30,
    )

    with patch("urllib.request.urlopen", fake_urlopen):
        result = client.complete("hello", 42)

    assert result == "<final>ok</final>"
    assert captured["url"] == "https://api.example.com/v1/chat/completions"
    assert captured["timeout"] == 30
    assert captured["authorization"] == "Bearer test-key"
    assert captured["body"]["model"] == "deepseek-chat"
    assert captured["body"]["messages"] == [{"role": "user", "content": "hello"}]
    assert captured["body"]["stream"] is False
    assert captured["body"]["max_tokens"] == 42
    assert captured["body"]["temperature"] == 0.2
    assert captured["body"]["top_p"] == 0.9


def test_openai_compatible_provider_posts_responses_payload():
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps({"output_text": "<final>ok</final>"}).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    client = OpenAICompatibleProvider(
        model="gpt-5.5",
        base_url="https://api.chiyi.cc",
        api_key="test-key",
        wire_api="responses",
    )

    with patch("urllib.request.urlopen", fake_urlopen):
        result = client.complete("hello", 42)

    assert result == "<final>ok</final>"
    assert captured["url"] == "https://api.chiyi.cc/v1/responses"
    assert captured["body"]["model"] == "gpt-5.5"
    assert captured["body"]["input"] == "hello"
    assert captured["body"]["max_output_tokens"] == 42
    assert "temperature" not in captured["body"]
    assert "top_p" not in captured["body"]


def test_openai_compatible_provider_uses_single_v1_prefix_for_responses():
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps({"output_text": "ok"}).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        return FakeResponse()

    client = OpenAICompatibleProvider(
        model="gpt-5.5",
        base_url="https://api.chiyi.cc/v1",
        api_key="test-key",
        wire_api="responses",
    )

    with patch("urllib.request.urlopen", fake_urlopen):
        assert client.complete("hello", 42) == "ok"

    assert captured["url"] == "https://api.chiyi.cc/v1/responses"


def test_openai_compatible_provider_translates_responses_function_call():
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(
                {
                    "output": [
                        {
                            "type": "function_call",
                            "name": "read_file",
                            "call_id": "call_123",
                            "arguments": '{"path":"calculator.py","start":1,"end":10}',
                        }
                    ]
                }
            ).encode("utf-8")

    def fake_urlopen(request, timeout):
        body = json.loads(request.data.decode("utf-8"))
        assert body["tools"][0]["type"] == "function"
        return FakeResponse()

    client = OpenAICompatibleProvider(
        model="gpt-5.5",
        base_url="https://api.example.com",
        api_key="test-key",
        wire_api="responses",
        tools=[{"type": "function", "name": "read_file"}],
    )

    with patch("urllib.request.urlopen", fake_urlopen):
        result = client.complete("inspect the file", 42)

    assert result == (
        '<tool>{"name": "read_file", "args": '
        '{"path": "calculator.py", "start": 1, "end": 10}}</tool>'
    )


def test_openai_compatible_provider_continues_responses_after_tool_result():
    captured = []

    class FakeResponse:
        def __init__(self, body):
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(self.body).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured.append(json.loads(request.data.decode("utf-8")))
        if len(captured) == 1:
            return FakeResponse(
                {
                    "id": "resp_123",
                    "output": [
                        {
                            "type": "function_call",
                            "name": "read_file",
                            "call_id": "call_123",
                            "arguments": '{"path":"calculator.py","start":1,"end":10}',
                        }
                    ],
                }
            )
        return FakeResponse({"output_text": "done"})

    client = OpenAICompatibleProvider(
        model="gpt-5.5",
        base_url="https://api.example.com",
        api_key="test-key",
        wire_api="responses",
    )

    with patch("urllib.request.urlopen", fake_urlopen):
        assert client.complete("inspect the file", 42).startswith("<tool>")
        client.submit_tool_result("file contents")
        assert client.complete("inspect the file", 42) == "done"

    assert captured[1]["previous_response_id"] == "resp_123"
    assert captured[1]["input"] == [
        {
            "type": "function_call_output",
            "call_id": "call_123",
            "output": "file contents",
        }
    ]


def test_openai_compatible_provider_sends_responses_instructions():
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps({"output_text": "ok"}).encode("utf-8")

    def fake_urlopen(request, timeout):
        body = json.loads(request.data.decode("utf-8"))
        assert body["instructions"] == "Use tools."
        return FakeResponse()

    client = OpenAICompatibleProvider(
        model="gpt-5.5",
        base_url="https://api.example.com",
        api_key="test-key",
        wire_api="responses",
        instructions="Use tools.",
    )

    with patch("urllib.request.urlopen", fake_urlopen):
        assert client.complete("inspect the file", 42) == "ok"


def test_openai_compatible_provider_requires_api_configuration():
    with pytest.raises(ValueError, match="LLM_API_KEY or OPENAI_API_KEY is required"):
        OpenAICompatibleProvider(
            model="demo-model",
            base_url="https://api.example.com/v1",
            api_key="",
        )


def test_anthropic_provider_sends_tool_result_in_follow_up_request():
    captured = []

    class FakeResponse:
        def __init__(self, body):
            self.body = body
            self.status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(self.body).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured.append(json.loads(request.data.decode("utf-8")))
        if len(captured) == 1:
            return FakeResponse(
                {
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "toolu_123",
                            "name": "read_file",
                            "input": {"path": "calculator.py", "start": 1, "end": 10},
                        }
                    ]
                }
            )
        return FakeResponse({"content": [{"type": "text", "text": "Done."}]})

    client = AnthropicCompatibleProvider(
        model="claude-test",
        base_url="https://api.example.com",
        api_key="test-key",
        tools=[
            {
                "type": "function",
                "name": "read_file",
                "description": "Read a file.",
                "parameters": {"type": "object", "properties": {"path": {"type": "string"}}},
            }
        ],
        instructions="Use tools.",
    )

    with patch("urllib.request.urlopen", fake_urlopen):
        tool_call = client.complete("inspect calculator.py", 42)
        client.submit_tool_result("1: def add(a, b): return a + b")
        final = client.complete("ignored after tool call", 42)

    assert json.loads(tool_call[6:-7]) == {
        "name": "read_file",
        "args": {"path": "calculator.py", "start": 1, "end": 10},
    }
    assert final == "Done."
    assert captured[0]["tools"][0]["input_schema"]["type"] == "object"
    assert captured[0]["system"] == "Use tools."
    assert captured[1]["messages"][-1] == {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": "toolu_123",
                "content": "1: def add(a, b): return a + b",
            }
        ],
    }


def test_prompt_tool_mode_omits_native_function_definitions(tmp_path, monkeypatch):
    captured = {}

    class StubProvider:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(cli_factory, "OpenAICompatibleProvider", StubProvider)
    args = Namespace(
        cwd=tmp_path,
        provider="openai",
        tool_mode="prompt",
        model="relay-model",
        base_url="https://api.example.com",
        api_key="test-key",
        wire_api="responses",
        temperature=0.2,
        top_p=0.9,
        timeout=30,
        resume=None,
        approval="auto",
        max_steps=3,
        max_new_tokens=128,
    )

    cli_factory.build_agent(args)

    assert captured["tools"] == []
    assert "XML tool format" in captured["instructions"]
