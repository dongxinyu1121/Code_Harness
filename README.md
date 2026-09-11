# Mini Coding Agent

Mini Coding Agent is a small, structured coding agent for working with a
local repository through an OpenAI-compatible or Anthropic-compatible model
provider.

The project is organized by responsibility:

```text
cli/         command-line entrypoint and interactive session
agent/       agent runtime, loop, parsing, and termination
providers/   model provider adapters
tools/       filesystem, search, shell, and delegation tools
workspace/   repository and workspace inspection
memory/      session persistence
tests/       automated tests
```

## Run

Run directly from the source tree:

```powershell
python -m cli
```

After installing the project:

```powershell
mini-coding-agent
```

Show command-line options:

```powershell
python -m cli --help
```

By default, the agent runs with `--approval auto`, so file writes, patches,
renames, deletes, and shell commands are allowed without an extra prompt. Use
`--approval ask` when you want to confirm risky tool calls one by one.

## Configuration

Copy `.env.example` to `.env` and configure the model provider. The local
`.env` file is ignored by Git.

For an OpenAI-compatible provider, the main settings are:

```text
LLM_BASE_URL=https://example.com/v1
LLM_API_KEY=your-api-key
LLM_MODEL=your-model
LLM_WIRE_API=chat_completions
```

The agent supports workspace inspection, file operations, bounded shell
commands, session persistence, approval policies, and bounded delegation.
