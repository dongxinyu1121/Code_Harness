&nbsp;
# Interactive Example

This is a hands-on example workflow for using `mini-coding-agent` with an
OpenAI-compatible API on a small Python project.

The flow is:

1. create a fresh repo
2. launch the agent
3. implement `binary_search.py`
4. edit the implementation
5. add `pytest` tests
6. run tests
7. fix anything that fails

This example assumes:

- you have configured `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL`
- you already cloned or forked `rasbt/mini-coding-agent`
- you already ran `uv sync` in your local `mini-coding-agent` folder

&nbsp;
## 1. Create a fresh repo

```bash
cd mini-coding-agent
mkdir -p ./tmp/binary-search-repo
cd ./tmp/binary-search-repo
git init
```

At this point the repo is basically empty:

```bash
ls -la
```

&nbsp;
## 2. Launch the agent

Open the agent from your `mini-coding-agent` clone, but point it at the new repo:

```bash
cd mini-coding-agent
uv run mini-coding-agent \
  --cwd ./tmp/binary-search-repo \
  --model "$env:LLM_MODEL" \
  --base-url "$env:LLM_BASE_URL"
```

<img src="https://sebastianraschka.com/images/github/mini-coding-agent/1.webp" width="500px">



&nbsp;

## 3. Ask it to implement binary search

At the `mini-coding-agent>` prompt, paste:

```text
Inspect this repository and create a minimal binary_search.py file. Implement an iterative binary_search(nums, target) function for a sorted list of integers. Return the index if the target exists and -1 if it does not. Keep the code very small.
```

After the agent finishes, inspect the result in another terminal or code editor. The contents are shown below:

<img src="https://sebastianraschka.com/images/github/mini-coding-agent/2.webp" width="200px">

&nbsp;
## 4. Ask it to edit the implementation

Now make a small follow-up change. Back in the agent REPL, paste:

```text
Update binary_search.py so it raises ValueError if the input list is not sorted in ascending order. Keep the implementation simple.
```

Check the file again:

<img src="https://sebastianraschka.com/images/github/mini-coding-agent/3.webp" width="300px">

&nbsp;
## 5. Ask it to add unit tests

Back in the REPL, paste:

```text
Create test_binary_search.py with pytest tests for found, missing, empty list, first element, last element, and unsorted input raising ValueError. Keep the tests small and readable.
```

Inspect the new test file:

<img src="https://sebastianraschka.com/images/github/mini-coding-agent/4.webp" width="250px">

&nbsp;
## 6. Ask it to run the tests

Back in the REPL, paste:

```text
Run pytest for this repo. If any test fails, fix the code or tests and rerun until everything passes.
```

You can also verify manually in a different terminal window:

```
uv run pytest tmp/binary-search-repo
```

&nbsp;
## 7. Inspect the final repo state

Check what changed:

```bash
cd mini-coding-agent
cd ./tmp/binary-search-repo
git status --short
```

You should now have:

- `README.md`
- `binary_search.py`
- `test_binary_search.py`

&nbsp;
## 8. Useful interactive commands

While the agent is running, these commands are available:

- `/help` shows the available slash commands and what each one does.
- `/memory` prints the agent's distilled working memory for the current session.
- `/session` shows the path to the saved session JSON file on disk.
- `/reset` clears the current conversation history and working memory.
- `/exit` leaves the interactive agent.
