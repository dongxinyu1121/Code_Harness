"""在工作区内部运行的文件系统工具。"""

from pathlib import Path


IGNORED_PATH_NAMES = {
    ".git",
    ".mini-coding-agent",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "venv",
}


def list_files(root, path_policy, args):
    path = path_policy.resolve(args.get("path", "."))
    if not path.is_dir():
        raise ValueError("path is not a directory")
    entries = [
        item
        for item in sorted(path.iterdir(), key=lambda item: (item.is_file(), item.name.lower()))
        if item.name not in IGNORED_PATH_NAMES
    ]
    lines = []
    for entry in entries[:200]:
        kind = "[D]" if entry.is_dir() else "[F]"
        lines.append(f"{kind} {entry.relative_to(root)}")
    return "\n".join(lines) or "(empty)"


def list_directory_tree(root, path_policy, args):
    """列出受限目录树，同时隐藏 Agent 内部状态。"""
    path = path_policy.resolve(args.get("path", "."))
    if not path.is_dir():
        raise ValueError("path is not a directory")
    max_depth = int(args.get("max_depth", 3))
    max_entries = int(args.get("max_entries", 200))
    if max_depth < 0 or max_depth > 10:
        raise ValueError("max_depth must be in [0, 10]")
    if max_entries < 1 or max_entries > 1000:
        raise ValueError("max_entries must be in [1, 1000]")

    lines = []
    count = 0

    def visit(current, depth):
        nonlocal count
        if depth > max_depth or count >= max_entries:
            return
        entries = [
            item
            for item in sorted(
                current.iterdir(),
                key=lambda item: (not item.is_dir(), item.name.lower()),
            )
            if item.name not in IGNORED_PATH_NAMES
        ]
        for entry in entries:
            if count >= max_entries:
                return
            relative = entry.relative_to(root)
            prefix = "  " * depth
            marker = "[D]" if entry.is_dir() else "[F]"
            lines.append(f"{prefix}{marker} {relative}")
            count += 1
            if entry.is_dir():
                visit(entry, depth + 1)

    visit(path, 0)
    return "\n".join(lines) or "(empty)"


def rename_file(root, path_policy, args):
    """重命名单个文件，并确保源路径和目标路径都在工作区内。"""
    source = path_policy.resolve(args["path"])
    destination = path_policy.resolve(args["new_path"])
    if not source.is_file():
        raise ValueError("source path is not a file")
    if destination.exists():
        raise ValueError("destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    source.rename(destination)
    return f"renamed {source.relative_to(root)} -> {destination.relative_to(root)}"


def delete_file(root, path_policy, args):
    """在调用方通过审批后删除单个文件。"""
    path = path_policy.resolve(args["path"])
    if not path.is_file():
        raise ValueError("path is not a file")
    path.unlink()
    return f"deleted {path.relative_to(root)}"


def read_file(root, path_policy, args):
    path = path_policy.resolve(args["path"])
    if not path.is_file():
        raise ValueError("path is not a file")
    start = int(args.get("start", 1))
    end = int(args.get("end", 200))
    if start < 1 or end < start:
        raise ValueError("invalid line range")
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    body = "\n".join(
        f"{number:>4}: {line}" for number, line in enumerate(lines[start - 1:end], start=start)
    )
    return f"# {path.relative_to(root)}\n{body}"


def write_file(root, path_policy, args):
    path = path_policy.resolve(args["path"])
    content = str(args["content"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return f"wrote {path.relative_to(root)} ({len(content)} chars)"


def patch_file(root, path_policy, args):
    path = path_policy.resolve(args["path"])
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
    path.write_text(text.replace(old_text, str(args["new_text"]), 1), encoding="utf-8")
    return f"patched {path.relative_to(root)}"
