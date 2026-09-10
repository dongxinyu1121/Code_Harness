# RepoDoctor 开发需求文档

> 项目定位：基于 `rasbt/mini-coding-agent` 进行工程化二次开发，构建一个面向 Python 项目的、测试反馈驱动的代码诊断与自主修复 Agent。
>
> 文档版本：v1.0  
> 开发阶段：MVP / Resume Project  
> 核心原则：**范围小、闭环完整、可量化评估、可在面试中讲清楚。**

---

## 1. 项目背景

`mini-coding-agent` 是一个用于解释 Coding Agent Harness 核心组成的轻量 Python 项目，已有以下基础能力：

- Agent Loop
- Workspace Context
- Structured Tools
- File Read / Write / Patch
- Shell Execution
- Code Search
- Session Persistence
- Working Memory
- Context Compression
- Tool Permission
- Delegation / Sub-Agent

原项目偏向教学和可读性，因此大量逻辑集中在单一 Python 文件中，并且当前模型调用主要围绕 Ollama。

RepoDoctor 不从零重写 Agent Harness，而是在理解和复用原项目核心机制的基础上，完成：

1. 工程化模块拆分；
2. LLM Provider 解耦；
3. 结构化测试执行能力；
4. BugFix Skill；
5. 测试反馈驱动的 Reflection / Retry；
6. 自动化 Bug Benchmark。

最终形成一个“小而完整”的代码修复 Agent。

---

# 2. 项目目标

RepoDoctor 的核心目标：

> 给定一个 Python 项目以及用户的错误描述，Agent 能够自主查看代码仓库、运行测试、分析错误、定位相关实现、修改代码、重新执行测试，并根据测试反馈继续修复，直到测试通过或达到终止条件。

目标闭环：

```text
User Task
    ↓
Inspect Repository
    ↓
Run Tests
    ↓
Analyze Failure
    ↓
Locate Relevant Code
    ↓
Patch Code
    ↓
Run Tests Again
    ↓
PASS ───────────────→ Finish
    │
    └── FAIL
          ↓
       Reflection
          ↓
       Retry
```

---

# 3. V1 范围冻结

## 3.1 V1 必须实现

- Python 项目支持
- pytest 测试框架支持
- Agent Loop
- Tool Calling
- Workspace Context
- Working Memory
- Session Persistence
- Context Management
- Ollama Provider（兼容保留）
- OpenAI-Compatible Provider
- File Tools
- Code Search Tool
- Shell Tool
- Structured TestRunner Tool
- Python BugFix Skill
- Reflection / Retry
- Agent Termination Strategy
- Benchmark Runner
- CLI 使用入口
- README 与架构说明

---

## 3.2 V1 明确不做

以下功能全部延期，禁止在 MVP 阶段随意扩展：

- React 前端
- Streamlit 前端
- FastAPI Web Server
- MCP
- RAG
- Vector Database
- Long-term Vector Memory
- Redis
- PostgreSQL
- Docker Sandbox
- Kubernetes
- GitHub 自动创建 PR
- Java / C++ / JavaScript 代码修复
- 复杂 Multi-Agent 编排
- 自动 Skill 生成
- GUI Dashboard

如开发过程中想到上述功能，记录到 `ROADMAP.md`，不得插入 V1 主线。

---

# 4. 关于原项目复现策略

## 4.1 不要求运行原版 Ollama Agent

本项目不要求在重构前下载本地大模型，也不要求先完整运行：

```text
mini-coding-agent
    ↓
Ollama
    ↓
Local Model
```

原因：

- 本项目最终主要使用 API 模型；
- 下载本地模型会增加不必要的时间成本；
- Provider 本身就是本项目第一批核心改造。

---

## 4.2 替代方案

开发顺序改为：

```text
阅读源码
    ↓
理解原有职责
    ↓
尽可能运行原仓库 Unit Tests
    ↓
模块化拆分
    ↓
Provider 抽象
    ↓
OpenAI-Compatible Provider
    ↓
云模型 Smoke Test
```

注意：

**“不运行原版 Ollama”不等于“不验证原始行为”。**

如果原项目自带测试，应优先安装测试依赖并运行测试，作为重构回归依据。

---

# 5. 总体架构

```text
                     ┌───────────────────────┐
                     │       User Task       │
                     └───────────┬───────────┘
                                 ↓
                     ┌───────────────────────┐
                     │      RepoDoctor       │
                     │      Agent Loop       │
                     └───────────┬───────────┘
                                 │
                ┌────────────────┼─────────────────┐
                ↓                ↓                 ↓
          Context Manager     Memory            Skill
                │                │                 │
                └────────────────┼─────────────────┘
                                 ↓
                          LLM Provider
                                 │
                     ┌───────────┴───────────┐
                     ↓                       ↓
                  Ollama              OpenAI-Compatible
                                 │
                                 ↓
                           Tool Registry
                                 │
          ┌──────────────┬───────┼────────┬──────────────┐
          ↓              ↓       ↓        ↓              ↓
       Filesystem      Search   Shell   TestRunner    Delegate
                                              │
                                              ↓
                                      Structured Result
                                              │
                                  ┌───────────┴───────────┐
                                  ↓                       ↓
                                PASS                    FAIL
                                  │                       │
                                  ↓                       ↓
                               Finish                Reflection
                                                          │
                                                          ↓
                                                       Retry
```

---

# 6. 推荐项目目录

```text
repodoctor/
│
├── main.py
├── config.py
├── .env.example
├── pyproject.toml
├── README.md
├── ROADMAP.md
├── LICENSE
│
├── agent/
│   ├── __init__.py
│   ├── agent.py
│   ├── loop.py
│   └── termination.py
│
├── providers/
│   ├── __init__.py
│   ├── base.py
│   ├── ollama.py
│   └── openai_compatible.py
│
├── tools/
│   ├── __init__.py
│   ├── base.py
│   ├── registry.py
│   ├── filesystem.py
│   ├── search.py
│   ├── shell.py
│   ├── test_runner.py
│   └── delegate.py
│
├── context/
│   ├── __init__.py
│   └── manager.py
│
├── memory/
│   ├── __init__.py
│   ├── working_memory.py
│   └── session_store.py
│
├── skills/
│   ├── __init__.py
│   ├── registry.py
│   └── builtin/
│       └── python_bugfix.md
│
├── reflection/
│   ├── __init__.py
│   └── reflector.py
│
├── workspace/
│   ├── __init__.py
│   └── snapshot.py
│
├── benchmark/
│   ├── __init__.py
│   ├── runner.py
│   ├── metrics.py
│   └── cases/
│
└── tests/
    ├── test_agent_loop.py
    ├── test_context_manager.py
    ├── test_memory.py
    ├── test_providers.py
    ├── test_tools.py
    └── test_test_runner.py
```

---

# 7. 模块职责

## 7.1 `agent/`

负责 Agent 核心编排。

### `agent.py`

负责：

- Agent 实例初始化
- Provider 注入
- Tool Registry 注入
- Context Manager 注入
- Memory 注入
- Skill 注入

禁止直接写具体模型 API 代码。

---

### `loop.py`

负责核心 Agent Loop：

```text
Build Context
    ↓
Call LLM
    ↓
Parse Response
    ↓
Tool Call ?
 ┌──────┴──────┐
YES            NO
 ↓              ↓
Execute Tool   Final
 ↓
Observation
 ↓
Update History / Memory
 ↓
Next Iteration
```

必须支持：

- `max_steps`
- Tool Call
- Tool Result
- Retry
- Final Answer
- 异常处理
- 重复工具调用检测

---

### `termination.py`

集中管理退出条件：

1. 测试全部通过；
2. Agent 返回 final；
3. 达到最大步数；
4. 连续重复相同工具调用；
5. Provider 连续失败；
6. Tool 出现不可恢复异常。

---

# 8. LLM Provider

## 8.1 目标

Agent Runtime 不直接依赖 Ollama。

定义统一接口：

```python
class BaseLLMProvider:
    def complete(self, messages, tools=None):
        raise NotImplementedError
```

Agent 只调用：

```python
provider.complete(...)
```

---

## 8.2 Ollama Provider

保留原项目兼容能力：

```text
OllamaProvider
    ↓
Ollama HTTP API
```

V1 不要求实际下载模型测试，但代码应保留适配。

---

## 8.3 OpenAI-Compatible Provider

V1 主要使用该 Provider。

目标兼容：

- OpenAI-compatible API
- DeepSeek compatible endpoint
- Qwen compatible endpoint
- 其他兼容 Chat Completions / Responses 风格的模型服务

配置通过环境变量：

```env
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=
LLM_API_KEY=
LLM_MODEL=
```

禁止在代码中硬编码 API Key。

---

## 8.4 验收标准

执行：

```bash
python main.py --help
```

能够看到 Provider 配置选项。

配置 API 后：

```bash
python main.py --workspace ./examples/demo
```

Agent 能够完成至少一次正常 LLM 调用。

---

# 9. Tool System

## 9.1 原有通用 Tool

至少支持：

- `list_files`
- `read_file`
- `write_file`
- `patch_file`
- `search_code`
- `run_shell`
- `delegate`

---

## 9.2 Tool Registry

所有工具统一注册：

```python
registry.register(tool)
```

Agent 不应直接：

```python
if tool_name == "read_file":
    ...
elif tool_name == "run_shell":
    ...
```

目标是减少硬编码。

---

# 10. Structured TestRunner Tool

这是 RepoDoctor V1 最核心的新增能力之一。

## 10.1 Tool 名称

```text
run_tests
```

---

## 10.2 V1 功能

自动执行 pytest，并解析：

- 总测试数量
- 通过数量
- 失败数量
- 执行耗时
- 失败测试名称
- 失败文件
- 核心 Traceback
- return code

---

## 10.3 推荐返回格式

```json
{
  "status": "failed",
  "framework": "pytest",
  "total": 12,
  "passed": 10,
  "failed": 2,
  "duration": 1.82,
  "failures": [
    {
      "test": "test_login",
      "file": "tests/test_auth.py",
      "traceback": "AssertionError ..."
    }
  ]
}
```

---

## 10.4 设计目标

避免直接把 pytest 大量 stdout 全部塞给 LLM。

流程：

```text
pytest raw output
       ↓
TestRunner Parser
       ↓
Structured Result
       ↓
Context Manager
       ↓
Agent
```

---

## 10.5 验收标准

准备一个包含：

```text
8 passed
2 failed
```

的测试项目。

`run_tests()` 必须正确返回：

- total = 10
- passed = 8
- failed = 2
- 至少一个失败 Traceback

---

# 11. Skill System

## 11.1 V1 目标

实现轻量 Skill，而不是 Hermes 风格复杂动态技能系统。

V1 只有一个内置 Skill：

```text
python_bugfix
```

---

## 11.2 Skill 文件

`skills/builtin/python_bugfix.md`

建议内容：

```markdown
# Python Bug Fix Skill

## Goal

Fix failing Python tests with minimal, evidence-based code changes.

## Workflow

1. Inspect repository structure.
2. Identify test configuration.
3. Run tests before modifying code.
4. Analyze failing tests and traceback.
5. Locate relevant implementation.
6. Read surrounding code before patching.
7. Apply the smallest reasonable fix.
8. Run affected tests.
9. Run full test suite.
10. Finish only after validation or a justified stop.
```

---

## 11.3 V1 Skill 使用方式

第一版不实现复杂 Router。

默认：

```text
Task
 ↓
python_bugfix Skill
 ↓
Agent Context
```

可保留 CLI：

```bash
--skill python_bugfix
```

为未来扩展做准备。

---

# 12. Working Memory

Working Memory 仅服务当前任务。

建议结构：

```json
{
  "task": "",
  "files_read": [],
  "files_modified": [],
  "failed_tests": [],
  "current_hypothesis": "",
  "previous_attempts": [],
  "important_notes": [],
  "iteration": 0
}
```

---

## 12.1 目标

避免 Agent 每轮都依赖完整 Transcript 才知道：

- 当前任务是什么；
- 哪些文件已经看过；
- 哪些修改已经做过；
- 哪些测试仍然失败；
- 当前推测是什么。

---

# 13. Session Memory

沿用并模块化原项目 Session Persistence。

至少支持：

```bash
python main.py --resume latest
```

保存：

- conversation transcript
- working memory
- workspace path
- task
- modified files
- execution state

V1 不实现向量检索型长期 Memory。

---

# 14. Context Management

Context Manager 负责控制 Prompt 长度。

## 14.1 必须支持

- Tool Output Truncation
- Old History Compression
- Duplicate File Read Compression
- Recent Messages Preservation
- Working Memory Injection
- Skill Injection
- Workspace Context Injection

---

## 14.2 推荐指标

记录：

```text
raw_context_chars
compressed_context_chars
```

如果 Provider 能获得 token usage，再记录：

```text
input_tokens
output_tokens
```

---

# 15. Reflection / Retry

这是 RepoDoctor V1 第二个核心新增能力。

## 15.1 触发条件

满足以下条件之一：

- Agent 修改代码后执行测试失败；
- 同一失败测试连续出现；
- 上一轮 Patch 未改变测试结果。

---

## 15.2 Reflection 输入

```text
Current Task
Previous Hypothesis
Previous Patch
Previous Test Result
Current Test Result
Relevant Working Memory
```

---

## 15.3 Reflection 输出

推荐结构：

```json
{
  "failure_reason": "",
  "previous_assumption_wrong": "",
  "new_hypothesis": "",
  "recommended_next_action": "",
  "avoid_repeating": ""
}
```

---

## 15.4 目标

禁止：

```text
Patch failed
    ↓
Agent 重复同样 Patch
```

目标：

```text
Patch
 ↓
Test Failure
 ↓
Reflection
 ↓
New Hypothesis
 ↓
New Action
```

---

# 16. Agent Loop

推荐伪代码：

```python
for step in range(max_steps):

    context = context_manager.build(
        task=task,
        history=history,
        memory=memory,
        skill=skill,
        workspace=workspace
    )

    response = provider.complete(
        messages=context,
        tools=tool_registry.schemas()
    )

    if response.is_final:
        return response

    tool_call = response.tool_call
    result = tool_registry.execute(tool_call)

    history.add(tool_call, result)
    memory.update(tool_call, result)

    if tool_call.name == "run_tests":
        if result.status == "passed":
            return success_result()

        if should_reflect(...):
            reflection = reflector.reflect(...)
            memory.add_reflection(reflection)

return max_steps_result()
```

---

# 17. 安全与权限

Coding Agent 能执行 Shell 和修改文件，因此必须保留基本安全边界。

## 17.1 Workspace Boundary

禁止：

```text
read_file("../../secret.txt")
```

所有文件操作必须限制在：

```text
workspace_root
```

---

## 17.2 Dangerous Tools

至少以下工具视为危险：

- write_file
- patch_file
- run_shell

支持三种审批模式：

```text
ask
auto
never
```

---

## 17.3 Shell

V1 不实现完整 Sandbox。

但至少应：

- 限制工作目录；
- 设置 timeout；
- 捕获 return code；
- 捕获 stdout/stderr；
- 防止无限运行。

---

# 18. Benchmark

Benchmark 是 V1 必须完成的部分。

## 18.1 Case 数量

第一版：

```text
10 ~ 20
```

个 Python Bug Case。

---

## 18.2 Bug 类型建议

```text
01_return_value
02_boundary_condition
03_wrong_if_condition
04_wrong_parameter
05_dict_key_error
06_list_index
07_exception_handling
08_file_path
09_class_method_logic
10_fastapi_response_logic
```

后续可继续增加。

---

## 18.3 每个 Case 必须包含

```text
buggy code
pytest tests
task description
expected behavior
```

---

## 18.4 核心指标

至少统计：

- Task Success Rate
- First-Pass Fix Rate
- Average Iterations
- Average Tool Calls
- Average Runtime
- Average Token Usage（Provider 支持时）
- Context Compression Ratio（可选）

---

## 18.5 成功定义

只有以下条件满足时任务才算成功：

```text
full pytest suite passed
```

不能仅以：

```text
Agent says "fixed"
```

作为成功依据。

---

# 19. CLI

V1 提供命令行使用方式。

示例：

```bash
python main.py \
  --workspace ./demo_project \
  --task "Fix the failing login tests"
```

建议支持：

```text
--workspace
--task
--provider
--model
--skill
--max-steps
--approval
--resume
```

---

# 20. 配置系统

配置优先级：

```text
CLI
 ↓
Environment Variables
 ↓
Default Config
```

`.env.example`：

```env
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=
LLM_API_KEY=
LLM_MODEL=
MAX_STEPS=20
TOOL_APPROVAL=ask
```

禁止上传真实 API Key。

---

# 21. 开发阶段

---

## Phase 0：源码理解与测试基线

### 目标

不运行 Ollama 模型，但完成原项目结构分析。

### 工作

- 阅读 `mini_coding_agent.py`
- 阅读 README
- 阅读 tests
- 绘制职责映射
- 安装 pytest 等测试依赖
- 尽可能运行原有 Unit Tests

### 验收

形成：

```text
SOURCE_MAPPING.md
```

明确：

```text
原函数 / 类
       ↓
目标模块
```

---

## Phase 1：模块化重构

### 目标

把单文件拆为分层目录。

### 原则

**只搬迁，不新增复杂逻辑。**

### 验收

- imports 正常
- 原测试尽可能继续通过
- main CLI 可启动

---

## Phase 2：Provider 抽象

### 工作

- BaseLLMProvider
- OllamaProvider
- OpenAICompatibleProvider
- Config
- API Key 环境变量

### 验收

API Provider 能正常返回模型结果。

这是 RepoDoctor 第一次真正进行端到端 LLM Smoke Test 的阶段。

---

## Phase 3：Structured TestRunner

### 工作

实现：

```text
run_tests
```

以及 pytest Parser。

### 验收

单元测试覆盖：

- 全部成功
- 单个失败
- 多个失败
- pytest 不存在
- timeout
- invalid workspace

---

## Phase 4：BugFix Skill

### 工作

- Skill Registry
- python_bugfix.md
- Skill Context Injection

### 验收

Agent Prompt 中可确认 Skill 已正确加载。

---

## Phase 5：Reflection / Retry

### 工作

- Reflector
- Reflection State
- Duplicate Patch Detection
- Retry Logic

### 验收

构造一个第一次修改必然无法修好的案例。

Agent 必须：

```text
Attempt 1
 ↓
FAIL
 ↓
Reflection
 ↓
Different Attempt
```

---

## Phase 6：Benchmark

### 工作

- 10~20 个 Bug Cases
- Benchmark Runner
- Metrics
- JSON / Markdown Result

### 输出

例如：

```text
benchmark_results.json
benchmark_report.md
```

---

## Phase 7：项目包装

完成：

- README
- Architecture Diagram
- Quick Start
- Benchmark Table
- Design Decisions
- Limitations
- Future Work
- GitHub 项目说明
- 简历描述

---

# 22. 测试要求

重要模块必须有单元测试。

至少覆盖：

```text
Provider
Tool Registry
Filesystem Boundary
TestRunner
Context Compression
Working Memory
Session Resume
Termination
Reflection
```

---

# 23. 代码质量要求

- Python 类型注解
- 函数职责单一
- 禁止超过必要长度的 God Class
- 模块之间通过接口协作
- 配置禁止散落硬编码
- 错误使用明确 Exception
- Tool 返回结构化结果
- 关键模块写 docstring
- 不为了“分层”制造无意义抽象

---

# 24. License 与开源来源说明

RepoDoctor 是在开源项目基础上的二次开发。

必须：

1. 保留原项目要求的许可证和版权声明；
2. README 明确说明项目基于 `rasbt/mini-coding-agent`；
3. 明确区分：
   - Upstream capabilities
   - RepoDoctor extensions
4. 简历中不得将原作者全部 Harness 工作描述为“从零自主实现”。

推荐 README 描述：

```text
RepoDoctor is an engineering extension of rasbt/mini-coding-agent,
focused on test-driven autonomous bug diagnosis and repair for Python projects.
```

---

# 25. RepoDoctor 的新增贡献边界

最终简历和 README 中应重点强调以下部分：

## 工程化改造

```text
Single-file educational harness
        ↓
Modular Agent Architecture
```

## Provider 解耦

```text
Ollama-only
    ↓
Provider Abstraction
    ↓
OpenAI-Compatible + Ollama
```

## Structured Test Tool

```text
Generic Shell
    ↓
Structured pytest TestRunner
```

## Skill

```text
Generic Coding Agent
    ↓
Python BugFix Skill
```

## Reflection

```text
Tool Feedback
    ↓
Failure Reflection
    ↓
New Hypothesis
```

## Benchmark

```text
Demo
 ↓
Quantitative Evaluation
```

---

# 26. 简历项目目标描述（开发完成后再定稿）

项目名称建议：

> **RepoDoctor —— 测试反馈驱动的代码诊断与自主修复 Agent**

技术关键词：

```text
Python
LLM
Agent Harness
Agent Loop
Tool Calling
Context Management
Working Memory
Skill
Reflection
pytest
OpenAI-Compatible API
```

完成后可以围绕以下四条组织简历：

1. Agent Harness 工程化重构；
2. Multi-Provider 与 Tool Calling；
3. TestRunner + Skill + Reflection；
4. Benchmark 实测结果。

所有性能数字必须以最终真实实验结果为准。

---

# 27. Definition of Done

只有同时满足以下要求，V1 才算完成：

- [ ] 项目完成模块化拆分
- [ ] CLI 可正常启动
- [ ] OpenAI-Compatible Provider 正常工作
- [ ] Agent 能调用 Tool
- [ ] Agent 能读取项目文件
- [ ] Agent 能运行 pytest
- [ ] TestRunner 返回结构化结果
- [ ] Agent 能修改代码
- [ ] 修改后能自动重新测试
- [ ] 测试失败能触发 Reflection
- [ ] Agent 能进行第二轮不同修复
- [ ] 测试通过能自动终止
- [ ] Session 可以保存和恢复
- [ ] Context 管理正常
- [ ] BugFix Skill 正常加载
- [ ] 至少 10 个 Benchmark Case
- [ ] 输出 Benchmark 数据
- [ ] README 完整
- [ ] 标注 upstream 开源来源
- [ ] 未泄露 API Key
- [ ] GitHub 仓库可供他人复现

---

# 28. 当前最重要的开发原则

## 原则 1：先完成 Agent 闭环，再增加功能

项目价值来自：

```text
LLM Decision
    ↓
Tool Action
    ↓
Environment Feedback
    ↓
New Decision
```

不是来自模块数量。

---

## 原则 2：每个 Phase 完成后必须保持项目可运行

禁止：

```text
一次拆完所有代码
↓
最后统一调 Bug
```

应该：

```text
拆一个模块
↓
测试
↓
Commit
↓
再拆下一个
```

---

## 原则 3：不要重新做 Hermes

任何新需求先问：

> 这个功能是否直接提升“Python 自动代码修复闭环”？

如果答案是否，则进入 Roadmap，不进入 V1。

---

## 原则 4：不要为了简历制造虚假复杂度

简单但可验证的：

```text
TestRunner
Reflection
Benchmark
```

比：

```text
MCP
Vector DB
Multi-Agent
```

堆砌更有价值。

---

# 29. 推荐 Git 开发分支

```bash
git checkout -b repodoctor
```

推荐按 Phase Commit：

```text
refactor: modularize agent harness

feat: add llm provider abstraction

feat: add structured pytest runner

feat: add python bugfix skill

feat: add reflection retry loop

feat: add bug repair benchmark

docs: complete architecture and benchmark report
```

---

# 30. 第一条实际开发任务

项目当前第一条任务不是运行 Ollama，而是：

> **阅读 `mini_coding_agent.py` 与测试代码，建立原源码到新目录结构的模块映射表，在不改变核心行为的前提下开始模块化重构。**

之后立即进入：

> **Provider Abstraction + OpenAI-Compatible API**

等 API Provider 跑通后，再进行第一次完整 Agent Smoke Test。

---

## 最终一句话定位

> RepoDoctor 是基于轻量 Coding Agent Harness 二次开发的 Python 自动代码修复 Agent，通过模块化 Agent Runtime、统一 LLM Provider、结构化 pytest 工具、BugFix Skill、测试失败 Reflection 以及自动 Benchmark，实现“诊断—修改—验证—反思—重试”的完整自主修复闭环。
