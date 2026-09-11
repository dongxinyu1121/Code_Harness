# Source Mapping

This document records the Phase 0 mapping from the upstream single-file
implementation to the planned RepoDoctor modules. It is a migration guide,
not a claim that the target modules already exist.

## Current Entry Points

| Current location | Responsibility | Planned module |
| --- | --- | --- |
| `now()` | UTC timestamp generation | `memory/session_store.py` or shared utility |
| `clip()` | Limit tool and prompt text | `context/manager.py` |
| `middle()` | Shorten terminal display text | `main.py` or CLI utility |
| `WorkspaceContext` | Discover repo root, Git state, and project docs | `workspace/snapshot.py` |
| `SessionStore` | Save, load, and find sessions | `memory/session_store.py` |
| `FakeModelClient` | Deterministic test provider | `providers/fake.py` or test support |
| `OpenAICompatibleProvider` | HTTP adapter for `/chat/completions` APIs | `providers/openai_compatible.py` |
| `MiniAgent.__init__()` | Assemble runtime dependencies and session state | `agent/runtime.py` |
| `MiniAgent.from_session()` | Rebuild an agent from persisted state | `agent/runtime.py` |
| `MiniAgent.remember()` | Keep bounded, de-duplicated memory entries | `memory/working_memory.py` |
| `MiniAgent.build_tools()` | Define tool schemas and handlers | `tools/registry.py` |
| `MiniAgent.build_prefix()` | Build stable instructions and tool prompt | `context/manager.py` |
| `MiniAgent.memory_text()` | Render working memory for the prompt | `memory/working_memory.py` |
| `MiniAgent.history_text()` | Compress and render transcript history | `context/manager.py` |
| `MiniAgent.prompt()` | Combine prefix, memory, history, and request | `context/manager.py` |
| `MiniAgent.record()` | Append history and persist session | `memory/session_store.py` |
| `MiniAgent.note_tool()` | Update memory after tool execution | `memory/working_memory.py` |
| `MiniAgent.ask()` | Compatibility facade for the model/tool/final-answer loop | `agent/loop.py` |
| `MiniAgent.run_tool()` | Validate, approve, execute, and clip tool result | `tools/registry.py` |
| `MiniAgent.repeated_tool_call()` | Compatibility wrapper for repeated recent tool calls | `agent/termination.py` |
| `MiniAgent.tool_example()` | Render correction examples for invalid calls | `tools/registry.py` |
| `MiniAgent.validate_tool()` | Validate tool arguments and paths | Individual tool modules plus registry |
| `MiniAgent.approve()` | Apply `ask`, `auto`, and `never` policy | `tools/permissions.py` |
| `MiniAgent.parse()` | Compatibility wrapper for model output parsing | `agent/response_parser.py` |
| `retry_notice()` | Create malformed-response feedback | `agent/response_parser.py` |
| `parse_xml_tool()` | Parse XML-style tool calls | `agent/response_parser.py` |
| `parse_attrs()`, `extract()`, `extract_raw()` | Parser helpers | `agent/response_parser.py` |
| `MiniAgent.reset()` | Clear history and working memory | `memory/session_store.py` or agent facade |
| `MiniAgent.path_is_within_root()` and `path()` | Compatibility wrappers for workspace path boundary | `tools/path_policy.py` |
| `tool_list_files()` and `tool_read_file()` | Compatibility wrappers for workspace filesystem reads | `tools/filesystem.py` |
| `tool_search()` | Compatibility wrapper for `rg` or fallback text search | `tools/search.py` |
| `tool_run_shell()` | Compatibility wrapper for bounded shell execution | `tools/shell.py` |
| `tool_write_file()` and `tool_patch_file()` | Compatibility wrappers for workspace file mutation | `tools/filesystem.py` |
| `tool_delegate()` | Compatibility wrapper for bounded read-only child agent | `tools/delegate.py` |
| `build_welcome()` | Terminal welcome screen | `cli/banner.py` |
| `build_agent()` | Compose workspace, provider, and session store | `cli/factory.py` |
| `build_arg_parser()` | Parse CLI configuration | `cli/config.py` |
| `main()` | One-shot and interactive CLI loop | `cli/app.py` |

## Current Tool Inventory

| Tool | Risk | Current behavior | RepoDoctor direction |
| --- | --- | --- | --- |
| `list_files` | Safe | List workspace entries and hide internal directories | Keep |
| `read_file` | Safe | Read a bounded line range | Keep |
| `search` | Safe | Search with `rg`, then use a Python fallback | Rename or alias as `search_code` |
| `run_shell` | Risky | Run a command in the repository root with timeout | Keep as a general tool |
| `write_file` | Risky | Write UTF-8 text inside the workspace | Keep |
| `patch_file` | Risky | Replace exactly one matching text block | Keep |
| `delegate` | Safe/read-only child | Run a bounded child agent | Keep with explicit depth limits |
| `run_tests` | New | Not present | Add structured pytest execution and result parsing |

The first runtime migration is complete. The structured packages are now the
source of truth; the former top-level `mini_coding_agent` compatibility module
has been removed. The Agent runtime and Responses tool definitions live in
`agent/runtime.py` and `tools/registry.py`.

## Agent Loop Mapping

The current `MiniAgent.ask()` loop is the behavioral reference:

```text
record user request
    -> build prompt
    -> call model
    -> parse tool, retry, or final
    -> validate and approve tool
    -> execute tool
    -> record observation
    -> update working memory
    -> repeat until final or limit
```

The first modular implementation must preserve this sequence. Test feedback,
reflection, and termination policies should be added after this behavior is
covered behind module interfaces.

## Current Provider Boundary

The current runtime calls:

```python
model_client.complete(prompt, max_new_tokens)
```

This is the first provider seam. The planned provider interface should hide
HTTP details from the agent loop:

```python
class BaseLLMProvider:
    def complete(self, prompt, max_new_tokens):
        raise NotImplementedError
```

`OpenAICompatibleProvider` is now the only real provider adapter. It uses
environment-based configuration or matching CLI flags:

```text
LLM_API_KEY
LLM_BASE_URL
LLM_MODEL
```

The previous local-model adapter was removed by project decision.

## Test Baseline

Baseline command:

```powershell
conda activate repodoctor
python -m pytest -q
```

Verified result on 2026-09-09:

```text
18 passed, 1 skipped
```

The skipped test depends on Windows symlink support. On this machine, pytest
may need an explicitly writable `--basetemp` directory because the default
user temporary directory can produce `WinError 5`.

## Existing Test Coverage

| Area | Tests |
| --- | --- |
| Agent loop and retry | `test_agent_runs_tool_then_final`, empty output retry, malformed tool retry |
| File mutation | XML `write_file`, exact `patch_file` replacement |
| Session and delegation | session resume, child agent delegation |
| Tool validation and safety | invalid risky args, repeated calls, parent escape, symlink escape, case variant |
| Workspace display | hidden internal state and long welcome paths |
| Context handling | prompt section formatting and duplicate read compression |
| Provider adapter | OpenAI-compatible Chat Completions payload construction |

## Uncovered or Partially Covered

- No real model or API smoke test
- No structured pytest runner
- No reflection state or retry hypothesis
- No explicit termination policy object
- No benchmark cases or success metrics
- CLI interactive input and approval are only lightly exercised
- Shell timeout and non-zero exit behavior need focused tests

## Phase 1 Migration Rules

1. Move one responsibility at a time.
2. Keep the existing public behavior and test results after each move.
3. Inject dependencies instead of constructing providers inside the loop.
4. Keep provider-specific HTTP payloads inside provider adapters.
5. Keep workspace path checks inside one path-policy module.
6. Do not add `run_tests`, reflection, or benchmark logic during the first
   mechanical split.

## Phase 1 Progress

- [x] Extract `WorkspaceContext` into `workspace/snapshot.py`
- [x] Extract `SessionStore` into `memory/session_store.py`
- [x] Extract model provider modules into `providers/`
- [x] Extract workspace path policy into `tools/path_policy.py`
- [x] Extract filesystem tools into `tools/filesystem.py`
- [x] Extract search into `tools/search.py`
- [x] Extract shell execution into `tools/shell.py`
- [x] Extract delegation implementation into `tools/delegate.py`
- [x] Extract model response parsing into `agent/response_parser.py`
- [x] Extract repeated-call and step-limit checks into `agent/termination.py`
- [x] Extract the main request loop into `agent/loop.py`
- [x] Preserve the existing test baseline: `18 passed, 1 skipped`
- [x] Replace Ollama with OpenAI-compatible API provider
