&nbsp;
# Code_Harness

This folder contains a small standalone coding agent:

- Stable CLI shim: `mini_coding_agent.py`
- CLI: `mini-coding-agent`

It is a minimal local agent loop with:

- workspace snapshot collection
- stable prompt plus turn state
- structured tools
- approval handling for risky tools
- transcript and memory persistence
- bounded delegation

The model backend uses an OpenAI-compatible API provider and reads its
credentials from CLI arguments or environment variables.

The CLI also supports Anthropic-compatible Messages endpoints. Set
`LLM_PROVIDER=anthropic`, then provide `ANTHROPIC_BASE_URL`,
`ANTHROPIC_AUTH_TOKEN` (or `ANTHROPIC_API_KEY`), and `ANTHROPIC_MODEL` in
your local `.env` file.

For an OpenAI-compatible relay that rejects native function calling, set
`LLM_TOOL_MODE=prompt`. The agent will use its XML tool-call format instead of
including API-level function definitions in the request.

## Module Layout

The command still starts through `mini_coding_agent.py`, but that file is now
only a compatibility shim. The CLI implementation is split by responsibility:

```text
mini_coding_agent.py       Stable shim that delegates to `cli.app:main`
cli/config.py               Environment loading and argument parsing
cli/factory.py              Dependency composition
cli/banner.py               Terminal welcome screen
cli/repl.py                 One-shot and interactive commands
cli/app.py                  The only application `main()` function
agent/runtime.py           MiniAgent runtime and tool lifecycle
agent/loop.py              model -> tool -> observation -> final loop
agent/response_parser.py   structured response parsing
agent/termination.py       repeated-call and step-limit policies
tools/registry.py          model-facing tool definitions
tools/filesystem.py        file operations
tools/search.py            code search
tools/shell.py             bounded shell execution
providers/                 OpenAI-compatible and fake model adapters
workspace/                 workspace and Git snapshot
memory/                    session persistence
```

This keeps the existing `python mini_coding_agent.py` and
`mini-coding-agent` commands compatible while giving new features a clear
module seam.

To run the modular CLI directly from the source tree, use:

```powershell
python -m cli
```

After installing the project with `pip install -e .`, the `mini-coding-agent`
command also points directly to `cli.app:main`.

<a href="https://magazine.sebastianraschka.com/p/components-of-a-coding-agent">
  <img src="https://substack-post-media.s3.amazonaws.com/public/images/49b97718-57f4-4977-99c8-8ad5c4d32af3_1548x862.png" width="500px">
</a>

<br>

**[The detailed tutorial: Components of a Coding Agent](https://magazine.sebastianraschka.com/p/components-of-a-coding-agent)**


&nbsp;
## Six Core Components

<a href="https://magazine.sebastianraschka.com/p/components-of-a-coding-agent">
  <img alt="Six core components of a coding agent" src="https://sebastianraschka.com/images/github/mini-coding-agent/six-components.webp" width="500px">
</a>

This coding harness is organized around six practical building blocks:

1. **Live repo context**  
   The agent collects stable workspace facts upfront, such as repo layout, instructions, and git state.
2. **Prompt shape and cache reuse**  
   A stable prompt prefix, which is separate from the changing request, transcript, and memory so repeated model calls can reuse the static parts efficiently.
3. **Structured tools, validation, and permissions**  
   The model works through named tools with checked inputs, workspace path validation, and approval gates instead of free-form arbitrary actions.
4. **Context reduction and output management**  
   Long outputs are clipped, repeated reads are deduplicated, and older transcript entries are compressed to keep prompt size under control.
5. **Transcripts, memory, and resumption**  
   The runtime keeps both a full durable transcript and a smaller working memory so sessions can be resumed while preserving important state via working memory.
6. **Delegation and bounded subagents**  
   Scoped subtasks can be delegated to helper agents that inherit enough context to help (but operate within limits).

&nbsp;
## Requirements

You need:

- Python 3.10+
- an API key for an OpenAI-compatible model service
- the service base URL and model name

Optional:

- `uv` for environment management and the `mini-coding-agent` CLI entry point

This project has no Python runtime dependency beyond the standard library, so you can run it directly with `python mini_coding_agent.py` if you do not want to use `uv`.

&nbsp;
## Configure An API Provider

The provider supports OpenAI-compatible Chat Completions and Responses endpoints.
For the Responses wire format:

```text
POST {OPENAI_BASE_URL}/responses
Authorization: Bearer {OPENAI_API_KEY}
```

Set the configuration in PowerShell:

```powershell
$env:OPENAI_BASE_URL="https://api.chiyi.cc"
$env:OPENAI_API_KEY="your-api-key"
$env:LLM_MODEL="gpt-5.5"
$env:LLM_WIRE_API="responses"
```

The API key is read at runtime and must not be committed to Git. You can also
put these values in a local `.env` file; `.env` is ignored by Git.

&nbsp;
## Project Setup

Clone the repo or your fork and change into it:

```bash
git clone https://github.com/rasbt/mini-coding-agent.git
cd mini-coding-agent
```

If you forked it first, use your fork URL instead:

```bash
git clone https://github.com/<your-github-user>/mini-coding-agent.git
cd mini-coding-agent
```



&nbsp;
## Basic Usage

Start the agent:

```bash
cd mini-coding-agent
uv run mini-coding-agent
```

Without `uv`, run the script directly:

```bash
cd mini-coding-agent
python mini_coding_agent.py
```

By default it reads:

- model: `LLM_MODEL`
- base URL: `LLM_BASE_URL` or `OPENAI_BASE_URL`
- API key: `LLM_API_KEY` or `OPENAI_API_KEY`
- approval: `ask`

For a concrete usage example, see [EXAMPLE.md](EXAMPLE.md).

&nbsp;
## Approval Modes

Risky tools such as shell commands and file writes are gated by approval.

- `--approval ask`
  prompts before risky actions (default and recommended)
- `--approval auto`
  allows risky actions automatically, including arbitrary command execution and file writes by the model; use only with trusted prompts and trusted repositories
- `--approval never`
  denies risky actions

Example:

```bash
uv run mini-coding-agent --approval auto
```



&nbsp;
## Resume Sessions

The agent saves sessions under the target workspace root in:

```text
.mini-coding-agent/sessions/
```

Resume the latest session:

```bash
uv run mini-coding-agent --resume latest
```


Resume a specific session:

```bash
uv run mini-coding-agent --resume 20260401-144025-2dd0aa
```


&nbsp;
## Interactive Commands

Inside the REPL, slash commands are handled directly by the agent instead of
being sent to the model as a normal task.

- `/help`
  shows the list of available interactive commands
- `/memory`
  prints the distilled session memory, including the current task, tracked files, and notes
- `/session`
  prints the path to the current saved session JSON file
- `/reset`
  clears the current session history and distilled memory but keeps you in the REPL
- `/exit`
  exits the interactive session
- `/quit`
  exits the interactive session; alias for `/exit`

&nbsp;
## Main CLI Flags

```bash
uv run mini-coding-agent --help
```

Without `uv`:

```bash
python mini_coding_agent.py --help
```

CLI flags are passed before the agent starts. Use them to choose the workspace,
model connection, resume behavior, approval mode, and generation limits.

Important flags:

- `--cwd`
  sets the workspace directory the agent should inspect and modify; default: `.`
- `--model`
  selects the model; defaults to `LLM_MODEL`
- `--base-url`
  selects the OpenAI-compatible API base URL; defaults to `LLM_BASE_URL` or `OPENAI_BASE_URL`
- `--api-key`
  supplies the API key; defaults to `LLM_API_KEY` or `OPENAI_API_KEY`
- `--timeout`
  controls how long the client waits for an API response; default: `900` seconds
- `--resume`
  resumes a saved session by id or uses `latest`; default: start a new session
- `--approval`
  controls how risky tools are handled: `ask`, `auto`, or `never`; default: `ask`
- `--max-steps`
  limits how many model and tool turns are allowed for one user request; default: `18`
- `--max-new-tokens`
  caps the model output length for each step; default: `1536`
- `--temperature`
  controls sampling randomness; default: `0.2`
- `--top-p`
  controls nucleus sampling for generation; default: `0.9`

&nbsp;
## Example

See [EXAMPLE.md](EXAMPLE.md)

&nbsp;
## Notes & Tips

- The agent expects the model to emit either `<tool>...</tool>` or `<final>...</final>`.
- Different API models will follow those instructions with different reliability.
- If the model does not follow the format well, use a stronger instruction-following model.
- The agent is intentionally small and optimized for readability, not robustness.
